# 関数一覧と概要

このドキュメントは、`gmo_coin_fx_api`ライブラリ内の主要なクラスと関数の概要を提供します。

## `class PublicAPI`
GMOコインFXのパブリックAPIにアクセスするためのクラス。

### メソッド

*   `get_status(self) -> dict`
    *   システム稼働状況を取得します。
*   `get_ticker(self) -> list`
    *   ティッカー情報を取得します。
*   `get_klines(self, symbol: str, price_type: str, interval: str, date: str) -> list`
    *   ローソク足情報を取得します。
*   `get_symbols(self) -> list`
    *   シンボル（銘柄）情報を取得します。

## `class PrivateAPI`
GMOコインFXのプライベートAPIにアクセスするためのクラス。APIキーとシークレットキーを必要とします。

### メソッド

*   `get_account_assets(self) -> list`
    *   口座の資産情報を取得します。
*   `get_orders(self, orderId: str | None = None, rootOrderId: str | None = None) -> list`
    *   注文情報を取得します。
*   `get_active_orders(self, symbol: str | None = None, page: int | None = None, count: int | None = None) -> list`
    *   有効な注文情報を取得します。
*   `get_executions(self, orderId: int | None = None, executionId: str | None = None) -> list`
    *   約定情報を取得します。
*   `get_latest_executions(self, symbol: str, count: int | None = None) -> list`
    *   最新の約定情報を取得します。
*   `get_open_positions(self, symbol: str | None = None, page: int | None = None, count: int | None = None) -> list`
    *   建玉情報を取得します。
*   `get_position_summary(self, symbol: str | None = None) -> list`
    *   建玉サマリー情報を取得します。
*   `speed_order(self, symbol: str, side: str, execution_type: str, size: str, price: str | None = None) -> list`
    *   スピード注文を実行します。
*   `order(self, symbol: str, side: str, execution_type: str, size: str, price: str | None = None, loseCutPrice: str | None = None) -> list`
    *   注文を実行します。
*   `ifd_order(self, symbol: str, side: str, execution_type: str, size: str, price: str | None = None, loseCutPrice: str | None = None, second_side: str | None = None, second_execution_type: str | None = None, second_price: str | None = None) -> list`
    *   IFD注文を実行します。
*   `ifo_order(self, symbol: str, side: str, execution_type: str, size: str, price: str | None = None, loseCutPrice: str | None = None, second_side: str | None = None, second_execution_type: str | None = None, second_price: str | None = None, third_side: str | None = None, third_execution_type: str | None = None, third_price: str | None = None) -> list`
    *   IFO注文を実行します。
*   `change_order(self, price: str, orderId: str | None = None, clientOrderId: str | None = None) -> list`
    *   注文を変更します。
*   `change_oco_order(self, price: str, loseCutPrice: str, orderId: str | None = None, clientOrderId: str | None = None) -> list`
    *   OCO注文を変更します。
*   `change_ifd_order(self, price: str, loseCutPrice: str, second_price: str, orderId: str | None = None, clientOrderId: str | None = None) -> list`
    *   IFD注文を変更します。
*   `change_ifo_order(self, price: str, loseCutPrice: str, second_price: str, third_price: str, orderId: str | None = None, clientOrderId: str | None = None) -> list`
    *   IFO注文を変更します。
*   `cancel_orders(self, orderId: str | None = None, clientOrderId: str | None = None) -> list`
    *   注文をキャンセルします。
*   `cancel_bulk_order(self, symbols: list[str]) -> list`
    *   複数の注文を一括キャンセルします。
*   `close_order(self, positionId: str, size: str | None = None, price: str | None = None, execution_type: str | None = None) -> list`
    *   ポジションをクローズします。
*   `get_ws_token(self) -> str`
    *   WebSocketトークンを取得します。
*   `extend_ws_token(self, token: str) -> dict`
    *   WebSocketトークンの有効期限を延長します。
*   `delete_ws_token(self, token: str) -> dict`
    *   WebSocketトークンを削除します。

## `class WebsocketAPI`
GMOコインFXのWebSocket APIにアクセスするためのクラス。

### メソッド

*   `start(self) -> None`
    *   WebSocket接続を開始します（非同期タスクとしてバックグラウンド実行）。
*   `close(self) -> None`
    *   WebSocket接続を停止し、リソースを解放します。
*   `subscribe_ticker(self, symbol: str, callback: Callable[[dict], Any]) -> None`
    *   ティッカー情報を購読します。
*   `subscribe_executions(self, callback: Callable[[dict], Any]) -> None`
    *   約定情報を購読します。
*   `subscribe_orders(self, callback: Callable[[dict], Any]) -> None`
    *   注文情報を購読します。
*   `subscribe_positions(self, callback: Callable[[dict], Any]) -> None`
    *   建玉情報を購読します。
*   `subscribe_position_summary(self, callback: Callable[[dict], Any], option: str = "PERIODIC") -> None`
    *   建玉サマリー情報を購読します。
