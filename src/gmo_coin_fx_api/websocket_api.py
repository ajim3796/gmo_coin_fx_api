import asyncio
import inspect
import json
import logging
from typing import Any, Callable

import niquests
from niquests.exceptions import ReadTimeout, RequestException

# PrivateAPIはトークン取得のために利用
from .private_api import PrivateAPI

logger = logging.getLogger(__name__)


class WebsocketAPI:
    """
    GMO Coin FX WebSocket API Client using niquests.
    """

    PUBLIC_WS_URL = "wss://forex-api.coin.z.com/ws/public/v1"
    PRIVATE_WS_URL_BASE = "wss://forex-api.coin.z.com/ws/private/v1"

    # サーバーからのPing間隔(60秒) + バッファ
    # この時間データ受信がない場合、ReadTimeoutが発生し再接続を試みる
    SOCKET_TIMEOUT = 70

    # 再接続待機時間(秒)
    RECONNECT_DELAY = 5

    def __init__(
        self,
        api_key: str | None = None,
        secret_key: str | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self.api_key = api_key
        self.secret_key = secret_key
        self.on_error = on_error

        self._running = False
        self._tasks: list[asyncio.Task] = []

        # コールバック管理
        self._callbacks: dict[str, Callable[[dict], Any]] = {}

        # 購読リスト (再接続時に再送信するため保持)
        self._public_subscriptions: list[dict] = []
        self._private_subscriptions: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start(self) -> None:
        """WebSocket接続を開始します（非同期タスクとしてバックグラウンド実行）"""
        self._running = True

        # Publicタスク起動
        if self._public_subscriptions:
            self._tasks.append(asyncio.create_task(self._run_public_loop()))

        # Privateタスク起動
        if self._private_subscriptions:
            if not self.api_key or not self.secret_key:
                raise ValueError("Private API subscriptions require api_key and secret_key.")
            self._tasks.append(asyncio.create_task(self._run_private_loop()))

    async def close(self) -> None:
        """WebSocket接続を停止し、リソースを解放します"""
        self._running = False

        # 全タスクのキャンセル
        for task in self._tasks:
            task.cancel()

        if self._tasks:
            # キャンセル完了を待機
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self._tasks = []
        logger.info("WebSocketAPI closed.")

    # ---------------------------------------------------------
    # Subscription Methods
    # ---------------------------------------------------------
    def subscribe_ticker(self, symbol: str, callback: Callable[[dict], Any]) -> None:
        self._callbacks["ticker"] = callback
        self._public_subscriptions.append({"command": "subscribe", "channel": "ticker", "symbol": symbol})

    def subscribe_executions(self, callback: Callable[[dict], Any]) -> None:
        self._callbacks["executionEvents"] = callback
        self._private_subscriptions.append({"command": "subscribe", "channel": "executionEvents"})

    def subscribe_orders(self, callback: Callable[[dict], Any]) -> None:
        self._callbacks["orderEvents"] = callback
        self._private_subscriptions.append({"command": "subscribe", "channel": "orderEvents"})

    def subscribe_positions(self, callback: Callable[[dict], Any]) -> None:
        self._callbacks["positionEvents"] = callback
        self._private_subscriptions.append({"command": "subscribe", "channel": "positionEvents"})

    def subscribe_position_summary(self, callback: Callable[[dict], Any], option: str = "PERIODIC") -> None:
        self._callbacks["positionSummaryEvents"] = callback
        self._private_subscriptions.append(
            {"command": "subscribe", "channel": "positionSummaryEvents", "option": option}
        )

    # ---------------------------------------------------------
    # Core Logic
    # ---------------------------------------------------------
    async def _run_ws_loop(self, url: str, subscriptions: list[dict], context_name: str):
        """
        niquestsを使用したWebSocket接続・受信のメインループ
        """
        while self._running:
            try:
                # niquests.AsyncSessionを使用 (コンテキストマネージャで確実にクローズ)
                async with niquests.AsyncSession() as session:
                    logger.info(f"[{context_name}] Connecting to {url} ...")

                    # 1. 接続 (HTTP GET -> Upgrade)
                    # timeoutを設定することで、サーバーからの無応答(ReadTimeout)を検知できるようにする
                    resp = await session.get(url, timeout=self.SOCKET_TIMEOUT)

                    # 2. ステータスコード確認 (101以外はWS接続失敗)
                    if resp.status_code != 101:
                        logger.error(f"[{context_name}] Connection failed. Status: {resp.status_code}")
                        await asyncio.sleep(self.RECONNECT_DELAY)
                        continue

                    logger.info(f"[{context_name}] Connected.")

                    # 3. 購読リクエスト送信
                    for sub_msg in subscriptions:
                        payload = json.dumps(sub_msg)
                        await resp.extension.send_payload(payload)
                        logger.debug(f"[{context_name}] Sent: {sub_msg}")

                    # 4. 受信ループ
                    while self._running:
                        try:
                            # next_payload() は内部でPing/Pongを自動処理する
                            # timeout時間内にデータが来なければ ReadTimeout が発生
                            payload = await resp.extension.next_payload()

                            # Noneが返ってきた場合はサーバー側からの正常切断
                            if payload is None:
                                logger.warning(f"[{context_name}] Server closed connection.")
                                break

                            # メッセージ処理
                            data = json.loads(payload)
                            await self._dispatch(data)

                        except ReadTimeout:
                            # タイムアウト（Pingも来ない＝回線切断の可能性）
                            # GMOは1分毎にPingを送るため、SOCKET_TIMEOUT(70s)設定ならここは通らないはず
                            # ここに来たら再接続のためにループを抜ける
                            logger.warning(f"[{context_name}] Read timeout. Reconnecting...")
                            break

                    # whileループを抜けたら (break or Exception)、Sessionは自動でcloseされる

            except (RequestException, Exception) as e:
                # ネットワークエラー等のハンドリング
                if not self._running:
                    break
                self._handle_error(e, context_name)
                await asyncio.sleep(self.RECONNECT_DELAY)

    # ---------------------------------------------------------
    # Loop Runners
    # ---------------------------------------------------------
    async def _run_public_loop(self):
        """Public API用ループ"""
        await self._run_ws_loop(self.PUBLIC_WS_URL, self._public_subscriptions, "Public")

    async def _run_private_loop(self):
        """Private API用ループ (トークン管理含む)"""
        while self._running:
            token = None
            try:
                # 1. トークン取得
                async with PrivateAPI(self.api_key, self.secret_key) as api:
                    token = await api.get_ws_token()

                if not token:
                    raise ValueError("Failed to retrieve WebSocket Token")

                ws_url = f"{self.PRIVATE_WS_URL_BASE}/{token}"

                # 2. WebSocket接続 (切断されるまでブロック)
                await self._run_ws_loop(ws_url, self._private_subscriptions, "Private")

            except Exception as e:
                if not self._running:
                    break
                self._handle_error(e, "Private(Auth)")
                await asyncio.sleep(self.RECONNECT_DELAY)

            finally:
                # 3. トークン削除 (行儀よく後始末)
                if token:
                    try:
                        async with PrivateAPI(self.api_key, self.secret_key) as api:
                            await api.delete_ws_token(token)
                    except Exception as e:
                        logger.warning(f"Failed to delete token: {e}")

    # ---------------------------------------------------------
    # Dispatcher
    # ---------------------------------------------------------
    async def _dispatch(self, data: dict):
        """受信データを適切なコールバックに配送"""
        channel = data.get("channel")
        callback = None

        if channel:
            # 通常のチャンネル通知
            callback = self._callbacks.get(channel)
        elif "ask" in data and "bid" in data:
            # Ticker (channelキーがない場合があるため形状で判定)
            callback = self._callbacks.get("ticker")
        else:
            logger.debug(f"Unknown message: {data}")

        if callback:
            try:
                if inspect.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def _handle_error(self, e: Exception, context: str):
        if isinstance(e, asyncio.CancelledError):
            return
        logger.error(f"[{context}] Error: {e}")
        if self.on_error:
            self.on_error(e)
