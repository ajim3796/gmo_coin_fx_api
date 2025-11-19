import asyncio
import json

import niquests

from .private_api import PrivateAPI


class WebsocketAPI:
    PUBLIC_WS_URL = "wss://forex-api.coin.z.com/ws/public/v1"
    PRIVATE_WS_URL_BASE = "wss://forex-api.coin.z.com/ws/private/v1"

    def __init__(self, on_error_callback=None, on_close_callback=None):
        self.on_error_callback = on_error_callback
        self.on_close_callback = on_close_callback
        self.session: niquests.AsyncSession | None = None
        self.ws_response: niquests.Response | None = None
        self._stop = asyncio.Event()
        self.channel_callbacks = {}

    async def _connect(self, uri, on_open_messages):
        try:
            self.session = niquests.AsyncSession()
            self.ws_response = await self.session.get(uri, timeout=None)
            print(f"Connected to {uri}")
            if not self.ws_response.extension:
                raise Exception("WebSocket拡張機能が利用できません。")

            if on_open_messages:
                assert self.ws_response is not None, "WebSocketレスポンスがありません。"
                for msg in on_open_messages:
                    await self.ws_response.extension.send_payload(json.dumps(msg))
                    print(f"Sent: {json.dumps(msg)}")

            while not self._stop.is_set():
                try:
                    assert self.ws_response is not None, "WebSocketレスポンスがありません。"
                    message = await self.ws_response.extension.next_payload()
                    if message is None:
                        break

                    parsed_message = json.loads(message)
                    channel = parsed_message.get("channel")

                    if channel and channel in self.channel_callbacks:
                        self.channel_callbacks[channel](parsed_message)
                    elif self.on_error_callback:
                        self.on_error_callback(f"Unknown channel or no callback registered for channel: {channel}")
                    else:
                        print(f"Received message for unknown channel or no callback: {parsed_message}")

                except niquests.exceptions.ReadTimeout:
                    continue
        except Exception as e:
            if self.on_error_callback:
                self.on_error_callback(e)
            else:
                print(f"Connection error: {e}")
        finally:
            if self.ws_response and self.ws_response.extension and not self.ws_response.extension.closed:
                assert self.ws_response is not None, "WebSocketレスポンスがありません。"
                await self.ws_response.extension.close()
            if self.session:
                await self.session.close()
            if self.on_close_callback:
                self.on_close_callback()
            print("Disconnected.")

    async def _start_private_channel_ws(self, channel_name: str, callback, option: str | None = None):
        """
        Private WebSocketに接続し、指定された単一チャネルを購読します。
        """
        self._stop.clear()
        self.channel_callbacks[channel_name] = callback

        try:
            async with PrivateAPI() as private_api:
                token = await private_api.get_ws_token()
            if not token:
                raise Exception("Failed to get WebSocket token.")

            uri = f"{self.PRIVATE_WS_URL_BASE}/{token}"

            subscribe_message = {"command": "subscribe", "channel": channel_name}
            if option:
                subscribe_message["option"] = option

            await self._connect(uri, [subscribe_message])

        except Exception as e:
            if self.on_error_callback:
                self.on_error_callback(e)
            else:
                print(f"Failed to start private WebSocket for {channel_name}: {e}")

    async def get_ticker_ws(self, symbol):
        """指定した銘柄の最新レートを受信します。subscribe後、最新レートが配信されます。"""
        self._stop.clear()
        subscribe_message = {
            "command": "subscribe",
            "channel": "ticker",
            "symbol": symbol,
        }
        await self._connect(self.PUBLIC_WS_URL, [subscribe_message])

    async def get_executions_ws(self, callback):
        """最新の約定情報通知を受信します。subscribe後、最新の約定情報通知が配信されます。"""
        await self._start_private_channel_ws("executionEvents", callback)

    async def get_orders_ws(self, callback):
        """最新の注文情報通知を受信します。subscribe後、最新の注文情報通知が配信されます。"""
        await self._start_private_channel_ws("orderEvents", callback)

    async def get_positions_ws(self, callback):
        """最新のポジション情報通知を受信します。subscribe後、最新のポジション情報通知が配信されます。"""
        await self._start_private_channel_ws("positionEvents", callback)

    async def get_position_summary_ws(self, callback, option: str | None = None):
        """最新のポジションサマリー情報通知を受信します。subscribe後、最新のポジションサマリー情報通知が配信されます。"""
        await self._start_private_channel_ws("positionSummaryEvents", callback, option)

    async def stop_ws(self):
        """WebSocket接続を停止します"""
        self._stop.set()
        if self.ws_response and self.ws_response.extension and not self.ws_response.extension.closed:
            assert self.ws_response is not None, "WebSocketレスポンスがありません。"
            await self.ws_response.extension.close()
        if self.session:
            await self.session.close()
        print("WebSocket connection stopped.")
