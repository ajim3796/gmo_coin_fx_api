from typing import Self

import niquests


class PublicAPI:
    BASE_URL = "https://forex-api.coin.z.com/public"

    def __init__(self) -> None:
        self.session: niquests.AsyncSession | None = None

    async def __aenter__(self) -> Self:
        self.session = niquests.AsyncSession()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.session:
            await self.session.close()

    async def _request(self, method: str, endpoint: str, params: dict | None = None) -> dict:
        """リクエストの共通処理関数

        Args:
            method (str): GET, POSTなど
            endpoint (str): APIのエンドポイント
            params (dict, optional): リクエストパラメータ

        Raises:
            Exception: API Request Error
            Exception: JSON Decode Error
            Exception: Status Error
        """
        assert self.session is not None, "セッションが初期化されていません。"
        try:
            path = self.BASE_URL + endpoint
            response = await self.session.request(method, path, params=params)
            response.raise_for_status()
            json_response = response.json()
            if json_response.get("status") == 0:
                raise Exception(
                    f"Status Error: status={json_response.get('status')}, message={json_response.get('messages', 'Unknown error')}"
                )
            elif json_response.get("data") is None:
                raise ValueError("API response did not contain 'data'.")
            return json_response
        except niquests.exceptions.JSONDecodeError:
            raise Exception("JSON Decode Error: Invalid JSON response")
        except niquests.exceptions.RequestException as e:
            raise Exception(f"API Request Error: {e}")

    async def get_status(self) -> dict:
        """外国為替FXの稼動状態を取得します。

        Returns:
            dict: ステータス情報
            - status (str): 外国為替FXステータス: MAINTENANCE, CLOSE, OPEN

        Examples:
        ```
        {
          "status": "OPEN"
        }
        ```
        """
        response = await self._request("GET", "/v1/status")
        return response.get("data", {})

    async def get_ticker(self) -> list:
        """全銘柄分の最新レートを取得します。

        Returns:
            list: 最新レートのリスト
            - symbol (str): 銘柄名
            - ask (str): 現在の買値
            - bid (str): 現在の売値
            - timestamp (str): 現在レートのタイムスタンプ
            - status (str): 外国為替FXステータス: CLOSE, OPEN

        Example:
        ```
        [
          {
            "symbol": "USD_JPY",
            "ask": "137.644",
            "bid": "137.632",
            "timestamp": "2018-03-30T12:34:56.789671Z",
            "status": "OPEN"
          },
          {
            "symbol": "EUR_JPY",
            "ask": "149.221",
            "bid": "149.181",
            "timestamp": "2023-05-19T02:51:24.516493Z",
            "status": "OPEN"
          }
        ]
        ```
        """
        response = await self._request("GET", "/v1/ticker")
        return response.get("data", [])

    async def get_klines(self, symbol: str, price_type: str, interval: str, date: str) -> list:
        """指定した銘柄の四本値を取得します。

        Args:
            symbol (str): 銘柄名
            price_type (str): BID, ASKを指定
            interval (str): 1min, 5min, 10min, 15min, 30min, 1hour, 4hour, 8hour, 12hour, 1day, 1week, 1month
            date (str): 1hourまではYYYYMMDD、4hourからはYYYY、20231028以降を指定可能

        Returns:
            list: 四本値のリスト
            - openTime (str): 開始時刻のunixタイムスタンプ(ミリ秒)
            - open (str): 始値
            - high (str): 高値
            - low (str): 安値
            - close (str): 終値

        Examples:
        ```
        [
          {
            "openTime":"1618588800000",
            "open":"141.365",
            "high":"141.368",
            "low":"141.360",
            "close":"141.362"
          },
          {
            "openTime":"1618588860000",
            "open":"141.362",
            "high":"141.369",
            "low":"141.361",
            "close":"141.365"
          }
        ]
        ```
        """
        params = {
            "symbol": symbol,
            "price_type": price_type,
            "interval": interval,
            "date": date,
        }
        response = await self._request("GET", "/v1/klines", params=params)
        return response.get("data", [])

    async def get_symbols(self) -> list:
        """取引ルールを取得します。

        Returns:
            list: 取引ルールのリスト
            - symbol (str): 銘柄名
            - minOpenOrderSize (str): 新規最小注文数量/回
            - maxOrderSize (str): 最大注文数量/回
            - sizeStep (str): 最小注文単位/回
            - tickSize (str): 注文価格の呼値

        Examples:
        ```
        [
          {
            "symbol": "USD_JPY",
            "minOpenOrderSize": "10000",
            "maxOrderSize": "500000",
            "sizeStep": "1",
            "tickSize": "0.001"
          }
        ]
        ```
        """
        response = await self._request("GET", "/v1/symbols")
        return response.get("data", [])
