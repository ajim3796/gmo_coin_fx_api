import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Self

import niquests

from .rate_limiter import RateLimiter


class PrivateAPI:
    end_point = "https://forex-api.coin.z.com/private"
    get_api_limiter = RateLimiter(max_calls=6, period=1)
    post_api_limiter = RateLimiter(max_calls=1, period=1)

    def __init__(self, api_key: str | None = None, secret_key: str | None = None) -> None:
        if api_key is None or secret_key is None:
            raise ValueError("APIキーとシークレットキーは必須です。")
        self.api_key: str = api_key
        self.secret_key: str = secret_key
        self.session: niquests.AsyncSession | None = None

    async def __aenter__(self) -> Self:
        self.session = niquests.AsyncSession()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.session:
            await self.session.close()

    def _generate_signature(self, timestamp: str, method: str, path: str, req_body: dict | None = None) -> str:
        if req_body is not None:
            text = timestamp + method + path + json.dumps(req_body)
        else:
            text = timestamp + method + path
        sign = hmac.new(
            bytes(self.secret_key.encode("ascii")),
            bytes(text.encode("ascii")),
            hashlib.sha256,
        ).hexdigest()
        return sign

    def _generate_headers(self, method: str, path: str, req_body: dict | None = None) -> dict:
        timestamp = "{0}000".format(int(time.mktime(datetime.now().timetuple())))
        sign = self._generate_signature(timestamp, method, path, req_body)
        headers = {
            "API-KEY": self.api_key,
            "API-TIMESTAMP": timestamp,
            "API-SIGN": sign,
        }
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        headers: dict | None = None,
        params: dict | None = None,
        req_body: dict | None = None,
    ) -> dict:
        """リクエストの共通処理関数

        Args:
            method (str): `GET` `POST` `PUT` `DELETE` など
            path (str): APIパス
            params (dict, optional): リクエストパラメータ
            headers (dict, optional): リクエストヘッダー
            req_body (dict, optional): リクエストボディ

        Raises:
            Exception: API Request Error
            Exception: JSON Decode Error
            Exception: Status Error
        """
        assert self.session is not None, "セッションが初期化されていません。"
        try:
            if method == "GET":
                response = await self.session.request(method, self.end_point + path, headers=headers, params=params)
            if method in ["POST", "PUT", "DELETE"]:
                response = await self.session.request(method, self.end_point + path, headers=headers, json=req_body)
            response.raise_for_status()
            json_response = response.json()
            if json_response.get("status") == 0:
                return json_response
            else:
                raise Exception(
                    f"Status Error: status={json_response.get('status')}, message={json_response.get('messages', 'Unknown error')}"
                )
        except niquests.exceptions.JSONDecodeError:
            raise Exception("JSON Decode Error: Invalid JSON response")
        except niquests.exceptions.RequestException as e:
            raise Exception(f"API Request Error: {e}")

    async def get_account_assets(self) -> list:
        """資産残高を取得します。

        Returns:
            list: 資産残高のリスト
            - equity (str): 時価評価総額
            - availableAmount (str): 取引余力
            - balance (str): 現金残高
            - estimatedTradeFee (str): 見込み手数料
            - margin (str): 拘束証拠金
            - marginRatio (str): 証拠金維持率
            - positionLossGain (str): 評価損益
            - totalSwap (str): 未決済スワップ
            - transferableAmount (str): 振替余力

        Examples:
        ```
        [
          {
            "equity": "120947776",
            "availableAmount": "89717102",
            "balance": "116884885",
            "estimatedTradeFee": "766.5",
            "margin": "31227908",
            "marginRatio": "406.3",
            "positionLossGain": "3884065.046",
            "totalSwap": "178825.439",
            "transferableAmount": "85654212"
          }
        ]
        ```
        """
        await PrivateAPI.get_api_limiter()
        method = "GET"
        path = "/v1/account/assets"
        headers = self._generate_headers(method, path)
        response = await self._request(method, path, headers=headers)
        return response.get("data", [])

    async def get_orders(self, orderId: str | None = None, rootOrderId: str | None = None) -> list:
        """指定した注文IDの注文情報を取得します。rootOrderId orderId いずれか1つが必須です。2つ同時には設定できません。

        Args:
            orderId (str, optional): 注文ID: カンマ区切りで最大10件まで指定可能
            rootOrderId (str, optional): 親注文ID: カンマ区切りで最大10件まで指定可能

        Raises:
            ValueError: rootOrderId orderId 2つ同時には設定できません。
            ValueError: rootOrderId orderId いずれか1つが必須です。

        Returns:
            list: 注文情報のリスト
            - rootOrderId (int): 親注文ID
            - clientOrderId (str): 顧客注文ID ※設定した場合のみ返却
            - orderId (int): 注文ID
            - symbol (str): 銘柄名
            - side (str): 売買区分 `BUY` `SELL`
            - orderType (str): 取引区分 `NORMAL` `OCO` `IFD` `IFDOCO` `LOSSCUT`
            - executionType (str): 注文タイプ `MARKET` `LIMIT` `STOP`
            - settleType (str): 決済区分 `OPEN` `CLOSE`
            - size (str): 注文数量
            - price (str): 注文価格 ※`LIMIT` `STOP`の場合のみ返却
            - status (str): 注文ステータス `WAITING` `ORDERED` `MODIFYING` `CANCELED` `EXECUTED` `EXPIRED`
            - cancelType (str): 取消区分 `USER` `INSUFFICIENT_COLLATERAL` `INSUFFICIENT_MARGIN` `SPEED` `OCO` `EXPIRATION` `PRICE_BOUND` `OUT_OF_SLIPPAGE_RANGE` ※statusが`CANCELED`または`EXPIRED`の場合のみ返却
            - expiry (str): 注文有効期限
            - timestamp (str): 注文日時

        Examples:
        ```
        [
          {
            "rootOrderId": 223456789,
            "clientOrderId": "sygngz1234",
            "orderId": 223456789,
            "symbol": "USD_JPY",
            "side": "BUY",
            "orderType": "NORMAL",
            "executionType": "LIMIT",
            "settleType": "OPEN",
            "size": "10000",
            "price": "140",
            "status": "EXECUTED",
            "expiry" : "20201113",
            "timestamp": "2020-10-14T20:18:59.343Z"
          },
          {
            "orderId": 123456789,
            "symbol": "CAD_JPY",
            "side": "SELL",
            "orderType": "NORMAL",
            "executionType": "LIMIT",
            "settleType": "CLOSE",
            "size": "10000",
            "price": "110",
            "status": "CANCELED",
            "cancelType": "USER",
            "expiry" : "20201113",
            "timestamp": "2020-10-14T20:18:59.343Z"
          }
        ]
        ```
        """
        await PrivateAPI.get_api_limiter()
        method = "GET"
        path = "/v1/orders"
        params = {}
        if orderId and rootOrderId:
            raise ValueError("rootOrderId orderId 2つ同時には設定できません。")
        elif orderId:
            params["orderId"] = orderId
        elif rootOrderId:
            params["rootOrderId"] = rootOrderId
        else:
            raise ValueError("rootOrderId orderId いずれか1つが必須です。")
        headers = self._generate_headers(method, path)
        response = await self._request(method, path, params=params, headers=headers)
        data = response.get("data", {})
        return data.get("list", [])

    async def get_active_orders(
        self, symbol: str | None = None, prevId: int | None = None, count: int | None = None
    ) -> list:
        """有効注文一覧を取得します。

        Args:
            symbol (str, optional): 銘柄名
            prevId (int, optional): 注文ID: 指定しない場合は最新から取得 指定した場合は指定した値より小さい注文IDを持つデータを取得
            count (int, optional): 取得件数: 指定しない場合は100(最大値)

        Returns:
            list: 有効注文のリスト
            - rootOrderId (int): 親注文ID
            - orderId (int): 注文ID
            - clientOrderId (str): 顧客注文ID ※設定した場合のみ返却
            - symbol (str): 銘柄名
            - side (str): 売買区分 `BUY` `SELL`
            - orderType (str): 取引区分 `NORMAL` `OCO` `IFD` `IFDOCO`
            - executionType (str): 注文タイプ `LIMIT` `STOP`
            - settleType (str): 決済区分 `OPEN` `CLOSE`
            - size (str): 注文数量
            - price (str): 注文価格
            - status (str): 注文ステータス `WAITING` `MODIFYING` `ORDERED`
            - expiry (str): 注文有効期限
            - timestamp (str): 注文日時

        Examples:
        ```
        [
          {
            "rootOrderId": 123456789,
            "orderId": 123456789,
            "clientOrderId": "abc123",
            "symbol": "USD_JPY",
            "side": "BUY",
            "orderType": "NORMAL",
            "executionType": "LIMIT",
            "settleType": "OPEN",
            "size": "10000",
            "price": "135.5",
            "status": "ORDERED",
            "expiry": "20190418",
            "timestamp": "2019-03-19T01:07:24.217Z"
          }
        ]
        ```
        """
        await PrivateAPI.get_api_limiter()
        method = "GET"
        path = "/v1/activeOrders"
        params = {}
        if symbol:
            params["symbol"] = symbol
        if prevId:
            params["prevId"] = prevId
        if count:
            params["count"] = count
        headers = self._generate_headers(method, path)
        response = await self._request(method, path, params=params, headers=headers)
        data: dict = response.get("data", {})
        return data.get("list", [])

    async def get_executions(self, orderId: int | None = None, executionId: str | None = None) -> list:
        """約定情報を取得します。orderId executionId いずれか1つが必須です。2つ同時には設定できません。

        Args:
            orderId (int, optional): 注文ID
            executionId (str, optional): 約定ID: カンマ区切りで最大10件まで指定可能

        Raises:
            ValueError: orderId executionId 2つ同時には設定できません。
            ValueError: orderId executionId いずれか1つが必須です。

        Returns:
            list: 約定情報のリスト
            - amount (str): 受渡金額
            - executionId (int): 約定ID
            - clientOrderId (str): 顧客注文ID ※設定した場合のみ返却
            - orderId (int): 注文ID
            - positionId (int): 建玉ID
            - symbol (str): 銘柄名
            - side (str): 売買区分 `BUY` `SELL`
            - settleType (str): 決済区分 `OPEN` `CLOSE`
            - size (str): 約定数量
            - price (str): 約定レート
            - lossGain (str): 決済損益
            - fee (str): 取引手数料
            - settledSwap (str): 決済スワップ
            - timestamp (str): 約定日時

        Examples:
        ```
        [
          {
            "amount":"16215.999",
            "executionId": 92123912,
            "clientOrderId": "aaaaa",
            "orderId": 223456789,
            "positionId": 2234567,
            "symbol": "USD_JPY",
            "side": "SELL",
            "settleType": "CLOSE",
            "size": "10000",
            "price": "141.251",
            "lossGain": "15730",
            "fee": "-30",
            "settledSwap":"515.999",
            "timestamp": "2020-11-24T21:27:04.764Z"
          },
          {
            "amount":"0",
            "executionId": 72123911,
            "clientOrderId": "bbbbb",
            "orderId": 123456789,
            "positionId": 1234567,
            "symbol": "USD_JPY",
            "side": "BUY",
            "settleType": "OPEN",
            "size": "10000",
            "price": "141.269",
            "lossGain": "0",
            "fee": "0",
            "settledSwap":"0",
            "timestamp": "2020-11-24T19:47:51.234Z"
          }
        ]
        ```
        """
        await PrivateAPI.get_api_limiter()
        method = "GET"
        path = "/v1/executions"
        params = {}
        if orderId and executionId:
            raise ValueError("orderId executionId 2つ同時には設定できません。")
        elif orderId:
            params["orderId"] = orderId
        elif executionId:
            params["executionId"] = executionId
        else:
            raise ValueError("orderId executionId いずれか1つが必須です。")
        headers = self._generate_headers(method, path)
        response = await self._request(method, path, params=params, headers=headers)
        data: dict = response.get("data", {})
        return data.get("list", [])

    async def get_latest_executions(self, symbol: str, count: int | None = None) -> list:
        """最新約定一覧を取得します。直近1日分から最新100件の約定情報を返します。

        Args:
            symbol (str): 銘柄名
            count (int, optional): 取得件数: 指定しない場合は100(最大値)

        Returns:
            list: 最新約定のリスト
            - amount (str): 受渡金額
            - executionId (int): 約定ID
            - clientOrderId (str): 顧客注文ID ※設定した場合のみ返却
            - orderId (int): 注文ID
            - positionId (int): 建玉ID
            - symbol (str): 銘柄名
            - side (str): 売買区分 `BUY` `SELL`
            - settleType (str): 決済区分 `OPEN` `CLOSE`
            - size (str): 約定数量
            - price (str): 約定レート
            - lossGain (str): 決済損益
            - fee (str): 取引手数料
            - settledSwap (str): 決済スワップ
            - timestamp (str): 約定日時

        Examples:
        ```
        [
          {
            "amount":"16215.999",
            "executionId": 92123912,
            "clientOrderId": "ccccc",
            "orderId": 223456789,
            "positionId": 2234567,
            "symbol": "USD_JPY",
            "side": "SELL",
            "settleType": "CLOSE",
            "size": "10000",
            "price": "141.251",
            "lossGain": "15730",
            "fee": "-30",
            "settledSwap":"515.999",
            "timestamp": "2020-11-24T21:27:04.764Z"
          }
        ]
        ```
        """
        await PrivateAPI.get_api_limiter()
        method = "GET"
        path = "/v1/latestExecutions"
        params: dict[str, str | int] = {"symbol": symbol}
        if count:
            params["count"] = count
        headers = self._generate_headers(method, path)
        response = await self._request(method, path, params=params, headers=headers)
        data: dict = response.get("data", {})
        return data.get("list", [])

    async def get_open_positions(
        self, symbol: str | None = None, prevId: int | None = None, count: int | None = None
    ) -> list:
        """有効建玉一覧を取得します。

        Args:
            symbol (str, optional): 銘柄名
            prevId (int, optional): 建玉ID: 指定しない場合は最新から取得、指定した場合は指定した値より小さい建玉IDを持つデータを取得
            count (int, optional): 取得件数: 指定しない場合は100(最大値)

        Returns:
            list: 有効建玉のリスト
            - positionId (int): 建玉ID
            - symbol (str): 銘柄名
            - side (str): 売買区分 `BUY` `SELL`
            - size (str): 建玉数量
            - orderedSize (str): 注文中数量
            - price (str): 建玉レート
            - lossGain (str): 評価損益
            - totalSwap (str): 累計スワップ
            - timestamp (str): 約定日時

        Examples:
        ```
        [
          {
            "positionId": 123456789,
            "symbol": "USD_JPY",
            "side": "BUY",
            "size": "10000",
            "orderedSize": "0",
            "price": "141.269",
            "lossGain": "-1980",
            "totalSwap":"0" ,
            "timestamp": "2019-03-21T05:18:09.011Z"
          }
        ]
        ```
        """
        await PrivateAPI.get_api_limiter()
        method = "GET"
        path = "/v1/openPositions"
        params = {}
        if symbol:
            params["symbol"] = symbol
        if prevId:
            params["prevId"] = prevId
        if count:
            params["count"] = count
        headers = self._generate_headers(method, path)
        response = await self._request(method, path, params=params, headers=headers)
        data: dict = response.get("data", {})
        return data.get("list", [])

    async def get_position_summary(self, symbol: str | None = None) -> list:
        """建玉サマリーを取得します。指定した銘柄の建玉サマリーを売買区分(買/売)ごとに取得できます。symbolパラメータ指定無しの場合は、保有している全銘柄の建玉サマリーを売買区分(買/売)ごとに取得します。

        Args:
            symbol (str, optional): 銘柄名: 指定しない場合は全銘柄分の建玉サマリーを返却

        Returns:
            list: 建玉サマリーのリスト
            - averagePositionRate (str): 平均建玉レート
            - positionLossGain (str): 評価損益
            - side (str): 売買区分 `BUY` `SELL`
            - sumOrderedSize (str): 合計注文中数量
            - sumPositionSize (str): 合計建玉数量
            - sumTotalSwap (str): 累計スワップ
            - symbol (str): 銘柄名

        Examples:
        ```
        [
          {
            "averagePositionRate": "140.043",
            "positionLossGain": "2322204.675",
            "side": "BUY",
            "sumOrderedSize": "0",
            "sumPositionSize": "1353339",
            "sumTotalSwap": "161600.404",
            "symbol": "USD_JPY"
          },
          {
            "averagePositionRate": "140.082",
            "positionLossGain": "-2588483.591",
            "side": "SELL",
            "sumOrderedSize": "20000",
            "sumPositionSize": "1481339",
            "sumTotalSwap": "-178353.217",
            "symbol": "USD_JPY"
          }
        ]
        ```
        """
        await PrivateAPI.get_api_limiter()
        method = "GET"
        path = "/v1/positionSummary"
        params = {}
        if symbol:
            params["symbol"] = symbol
        headers = self._generate_headers(method, path)
        response = await self._request(method, path, params=params, headers=headers)
        data: dict = response.get("data", {})
        return data.get("list", [])

    async def speed_order(
        self,
        symbol: str,
        side: str,
        size: str,
        clientOrderId: str | None = None,
        lowerBound: str | None = None,
        upperBound: str | None = None,
        isHedgeable: bool = False,
    ) -> list:
        """スピード注文をします。

        Args:
            symbol (str): 銘柄名
            side (str): 売買区分 `BUY` `SELL`
            size (str): 注文数量
            clientOrderId (str, optional): 顧客注文ID ※36文字以内の半角英数字の組合わせのみ使用可能
            lowerBound (str, optional): 成立下限価格: `SELL`の場合に指定可能
            upperBound (str, optional): 成立上限価格: `BUY`の場合に指定可能
            isHedgeable (bool, optional): 両建て可能フラグ `True` `False` (デフォルトは`False`)

        Returns:
            list: 注文情報のリスト
            - rootOrderId (int): 親注文ID
            - clientOrderId (str): 	顧客注文ID ※設定した場合のみ返却
            - orderId (int): 注文ID
            - symbol (str): 取扱銘柄はこちら
            - side (str): 売買区分 `BUY` `SELL`
            - orderType (str): 取引区分 `NORMAL`
            - executionType (str): 注文タイプ `MARKET`
            - settleType (str): 決済区分 `OPEN` `CLOSE`
            - size (str): 注文数量
            - status (str): 注文ステータス `EXECUTED` `EXPIRED`
            - cancelType (str): 取消区分 `PRICE_BOUND` ※statusが`EXPIRED`の場合のみ返却
            - timestamp (str): 注文日時

        Examples:
        ```
        [
          {
            "rootOrderId": 123456789,
            "clientOrderId": "sygngz1234",
            "orderId": 123456789,
            "symbol": "USD_JPY",
            "side": "BUY",
            "orderType": "NORMAL",
            "executionType": "MARKET",
            "settleType": "OPEN",
            "size": "10000",
            "status": "EXECUTED",
            "timestamp": "2019-03-19T02:15:06.059Z"
          }
        ]
        ```
        """
        await PrivateAPI.post_api_limiter()
        method = "POST"
        path = "/v1/speedOrder"
        req_body = {
            "symbol": symbol,
            "side": side,
            "size": size,
            "isHedgeable": isHedgeable,
        }
        if clientOrderId:
            req_body["clientOrderId"] = clientOrderId
        if lowerBound:
            req_body["lowerBound"] = lowerBound
        if upperBound:
            req_body["upperBound"] = upperBound
        headers = self._generate_headers(method, path, req_body)
        response = await self._request(method, path, headers=headers, req_body=req_body)
        return response.get("data", [])

    async def order(
        self,
        symbol: str,
        side: str,
        size: str,
        executionType: str,
        clientOrderId: str | None = None,
        limitPrice: str | None = None,
        stopPrice: str | None = None,
        lowerBound: str | None = None,
        upperBound: str | None = None,
    ) -> list:
        """新規注文をします。

        Args:
            symbol (str): 銘柄名
            side (str): 売買区分 `BUY` `SELL`
            size (str): 注文数量
            executionType (str): 注文タイプ `MARKET` `LIMIT` `STOP` `OCO`
            clientOrderId (str, optional): 顧客注文ID ※36文字以内の半角英数字の組合わせのみ使用可能
            limitPrice (str, optional): 指値注文レート: `LIMIT` `OCO`の場合は必須
            stopPrice (str, optional): 逆指値注文レート: `STOP` `OCO`の場合は必須
            lowerBound (str, optional): 成立下限価格: executionType:`MARKET` side:`SELL`の場合に指定可能
            upperBound (str, optional): 成立上限価格: executionType:`MARKET` side:`BUY`の場合に指定可能

        Raises:
            ValueError: limitPrice は注文タイプが LIMIT または OCO の場合に必須です。
            ValueError: stopPrice は注文タイプが STOP または OCO の場合に必須です。

        Returns:
            list: 注文情報のリスト

        Examples:
        ```
        [
          {
            "rootOrderId": 123456789,
            "clientOrderId": "abc123",
            "orderId": 123456789,
            "symbol": "USD_JPY",
            "side": "BUY",
            "orderType": "NORMAL",
            "executionType": "LIMIT",
            "settleType": "OPEN",
            "size": "10000",
            "price": "130",
            "status": "WAITING",
            "expiry" : "20190418",
            "timestamp": "2019-03-19T02:15:06.059Z"
          }
        ]
        ```
        """
        await PrivateAPI.post_api_limiter()
        method = "POST"
        path = "/v1/order"
        req_body = {
            "symbol": symbol,
            "side": side,
            "size": size,
            "executionType": executionType,
        }
        if clientOrderId:
            req_body["clientOrderId"] = clientOrderId
        if executionType == "LIMIT" or executionType == "OCO":
            if limitPrice is None:
                raise ValueError("limitPrice は注文タイプが LIMIT または OCO の場合に必須です。")
            req_body["limitPrice"] = limitPrice
        if executionType == "STOP" or executionType == "OCO":
            if stopPrice is None:
                raise ValueError("stopPrice は注文タイプが STOP または OCO の場合に必須です。")
            req_body["stopPrice"] = stopPrice
        if executionType == "MARKET":
            if side == "SELL" and lowerBound:
                req_body["lowerBound"] = lowerBound
            elif side == "BUY" and upperBound:
                req_body["upperBound"] = upperBound
        headers = self._generate_headers(method, path, req_body)
        response = await self._request(method, path, headers=headers, req_body=req_body)
        return response.get("data", [])

    async def ifd_order(
        self,
        symbol: str,
        firstSide: str,
        firstExecutionType: str,
        firstSize: str,
        firstPrice: str,
        secondExecutionType: str,
        secondSize: str,
        secondPrice: str,
        clientOrderId: str | None = None,
    ) -> list:
        """IFD注文をします。

        Args:
            symbol (str): 銘柄名
            firstSide (str): 1次売買区分 `BUY` `SELL`
            firstExecutionType (str): 1次注文タイプ `LIMIT` `STOP`
            firstSize (str): 1次注文数量
            firstPrice (str): 1次注文レート
            secondExecutionType (str): 2次注文タイプ `LIMIT` `STOP`
            secondSize (str): 2次注文数量
            secondPrice (str): 2次注文レート
            clientOrderId (str, optional): 顧客注文ID ※36文字以内の半角英数字の組合わせのみ使用可能

        Returns:
            list: 注文情報のリスト
            - rootOrderId (int): 親注文ID
            - clientOrderId (str): 顧客注文ID ※設定した場合のみ返却
            - orderId (int): 注文ID
            - symbol (str): 銘柄名
            - side (str): 売買区分: `BUY` `SELL`
            - orderType (str): 取引区分: `IFD`
            - executionType (str): 注文タイプ: `LIMIT` `STOP`
            - settleType (str): 決済区分: `OPEN` `CLOSE`
            - size (str): 注文数量
            - price (str): 注文価格
            - status (str): 注文ステータス: `WAITING` `ORDERED` `EXECUTED`
            - expiry (str): 注文有効期限
            - timestamp (str): 注文日時

        Examples:
        ```
        [
          {
            "rootOrderId": 123456789,
            "clientOrderId": "abc123",
            "orderId": 123456789,
            "symbol": "USD_JPY",
            "side": "BUY",
            "orderType": "IFD",
            "executionType": "LIMIT",
            "settleType": "OPEN",
            "size": "10000",
            "price": "130",
            "status": "WAITING",
            "expiry" : "20190418",
            "timestamp": "2019-03-19T02:15:06.059Z"
          },
          {
            "rootOrderId": 123456789,
            "clientOrderId": "abc123",
            "orderId": 123456790,
            "symbol": "USD_JPY",
            "side": "SELL",
            "orderType": "IFD",
            "executionType": "LIMIT",
            "settleType": "CLOSE",
            "size": "10000",
            "price": "145",
            "status": "WAITING",
            "expiry" : "20190418",
            "timestamp": "2019-03-19T02:15:06.059Z"
          }
        ]
        """
        await PrivateAPI.post_api_limiter()
        method = "POST"
        path = "/v1/ifdOrder"
        req_body = {
            "symbol": symbol,
            "firstSide": firstSide,
            "firstExecutionType": firstExecutionType,
            "firstSize": firstSize,
            "firstPrice": firstPrice,
            "secondExecutionType": secondExecutionType,
            "secondSize": secondSize,
            "secondPrice": secondPrice,
        }
        if clientOrderId:
            req_body["clientOrderId"] = clientOrderId
        headers = self._generate_headers(method, path, req_body)
        response = await self._request(method, path, headers=headers, req_body=req_body)
        return response.get("data", [])

    async def ifo_order(
        self,
        symbol: str,
        firstSide: str,
        firstExecutionType: str,
        firstSize: str,
        firstPrice: str,
        secondSize: str,
        secondLimitPrice: str | None = None,
        secondStopPrice: str | None = None,
        clientOrderId: str | None = None,
    ) -> list:
        """IFDOCO注文をします。

        Args:
            symbol (str): 銘柄名
            firstSide (str): 1次売買区分 `BUY` `SELL`
            firstExecutionType (str): 1次注文タイプ `LIMIT` `STOP`
            firstSize (str): 1次注文数量
            firstPrice (str): 1次注文レート
            secondSize (str): 2次注文数量
            secondLimitPrice (str, optional): 2次指値注文レート
            secondStopPrice (str, optional): 2次逆指値注文レート
            clientOrderId (str, optional): 顧客注文ID ※36文字以内の半角英数字の組合わせのみ使用可能

        Returns:
            dict: 注文情報の辞書
            - rootOrderId (int): 親注文ID
            - clientOrderId (str): 顧客注文ID ※設定した場合のみ返却
            - orderId (int): 注文ID
            - symbol (str): 銘柄名
            - side (str): 売買区分: `BUY` `SELL`
            - orderType (str): 取引区分: `IFDOCO`
            - executionType (str): 注文タイプ: `LIMIT` `STOP`
            - settleType (str): 決済区分: `OPEN` `CLOSE`
            - size (str): 注文数量
            - price (str): 注文価格
            - status (str): 注文ステータス: `WAITING` `ORDERED` `EXECUTED`
            - expiry (str): 注文有効期限
            - timestamp (str): 注文日時

        Examples:
        [
          {
            "rootOrderId": 123456789,
            "clientOrderId": "abc123",
            "orderId": 123456789,
            "symbol": "USD_JPY",
            "side": "BUY",
            "orderType": "IFDOCO",
            "executionType": "LIMIT",
            "settleType": "OPEN",
            "size": "10000",
            "price": "135",
            "status": "WAITING",
            "expiry" : "20190418",
            "timestamp": "2019-03-19T02:15:06.059Z"
          },
          {
            "rootOrderId": 123456789,
            "clientOrderId": "abc123",
            "orderId": 123456790,
            "symbol": "USD_JPY",
            "side": "SELL",
            "orderType": "IFDOCO",
            "executionType": "LIMIT",
            "settleType": "CLOSE",
            "size": "10000",
            "price": "140",
            "status": "WAITING",
            "expiry" : "20190418",
            "timestamp": "2019-03-19T02:15:06.059Z"
          },
          {
            "rootOrderId": 123456789,
            "clientOrderId": "abc123",
            "orderId": 123456791,
            "symbol": "USD_JPY",
            "side": "SELL",
            "orderType": "IFDOCO",
            "executionType": "STOP",
            "settleType": "CLOSE",
            "size": "10000",
            "price": "132",
            "status": "WAITING",
            "expiry" : "20190418",
            "timestamp": "2019-03-19T02:15:06.059Z"
          }
        ]
        """
        await PrivateAPI.post_api_limiter()
        method = "POST"
        path = "/v1/ifoOrder"
        req_body = {
            "symbol": symbol,
            "firstSide": firstSide,
            "firstExecutionType": firstExecutionType,
            "firstSize": firstSize,
            "firstPrice": firstPrice,
            "secondSize": secondSize,
        }
        if secondLimitPrice:
            req_body["secondLimitPrice"] = secondLimitPrice
        if secondStopPrice:
            req_body["secondStopPrice"] = secondStopPrice
        if clientOrderId:
            req_body["clientOrderId"] = clientOrderId
        headers = self._generate_headers(method, path, req_body)
        response = await self._request(method, path, headers=headers, req_body=req_body)
        return response.get("data", [])

    async def change_order(self, price: str, orderId: str | None = None, clientOrderId: str | None = None) -> list:
        """注文変更をします。orderId clientOrderIdいずれか1つが必須です。2つ同時には設定できません。

        Args:
            price (str): 注文レート
            orderId (str, optional): 注文ID
            clientOrderId (str, optional): 顧客注文ID ※36文字以内の半角英数字の組合わせのみ使用可能

        Raises:
            ValueError: orderId clientOrderId 2つ同時には設定できません。
            ValueError: orderId clientOrderId いずれか1つが必須です。

        Returns:
            list: 注文情報のリスト
            - rootOrderId (int): 親注文ID
            - clientOrderId (str): 顧客注文ID ※設定した場合のみ返却
            - orderId (int): 注文ID
            - symbol (str): 銘柄名
            - side (str): 売買区分: `BUY` `SELL`
            - orderType (str): 取引区分: `NORMAL`
            - executionType (str): 注文タイプ: `LIMIT` `STOP`
            - settleType (str): 決済区分: `OPEN` `CLOSE`
            - size (str): 注文数量
            - price (str): 注文価格
            - status (str): 注文ステータス: `ORDERED` `MODIFYING` `EXECUTED`
            - expiry (str): 注文有効期限
            - timestamp (str): 注文日時

        Examples:
        ```
        [
          {
            "rootOrderId": 123456789,
            "clientOrderId": "abc123",
            "orderId": 123456789,
            "symbol": "USD_JPY",
            "side": "BUY",
            "orderType": "NORMAL",
            "executionType": "LIMIT",
            "settleType": "OPEN",
            "size": "10000",
            "price": "139",
            "status": "ORDERED",
            "expiry" : "20190418",
            "timestamp": "2019-03-19T02:15:06.059Z"
          }
        ]
        ```
        """
        await PrivateAPI.post_api_limiter()
        method = "POST"
        path = "/v1/changeOrder"
        req_body = {"price": price}
        if orderId and clientOrderId:
            raise ValueError("orderId clientOrderId 2つ同時には設定できません。")
        elif orderId:
            req_body["orderId"] = orderId
        elif clientOrderId:
            req_body["clientOrderId"] = clientOrderId
        else:
            raise ValueError("orderId clientOrderId いずれか1つが必須です。")
        headers = self._generate_headers(method, path, req_body)
        response = await self._request(method, path, headers=headers, req_body=req_body)
        return response.get("data", [])

    async def change_oco_order(
        self,
        rootOrderId: int | None = None,
        clientOrderId: str | None = None,
        limitPrice: str | None = None,
        stopPrice: str | None = None,
    ) -> list:
        """OCO注文変更をします。rootOrderId clientOrderIdいずれか1つが必須です。2つ同時には設定できません。limitPrice stopPrice 両方もしくはどちらか1つが必須です。

        Args:
            rootOrderId (int, optional): 親注文ID
            clientOrderId (str, optional): 顧客注文ID ※36文字以内の半角英数字の組合わせのみ使用可能
            limitPrice (str, optional): 指値注文レート
            stopPrice (str, optional): 逆指値注文レート

        Raises:
            ValueError: rootOrderId clientOrderId 2つ同時には設定できません。
            ValueError: rootOrderId clientOrderId いずれか1つが必須です。
            ValueError: limitPrice stopPrice 両方もしくはどちらか1つが必須です。

        Returns:
            list: 注文情報のリスト
            - rootOrderId (int): 親注文ID
            - clientOrderId (str): 顧客注文ID ※設定した場合のみ返却
            - orderId (int): 注文ID
            - symbol (str): 銘柄名
            - side (str): 売買区分: `BUY` `SELL`
            - orderType (str): 取引区分: `OCO`
            - executionType (str): 注文タイプ: `LIMIT` `STOP`
            - settleType (str): 決済区分: `OPEN` `CLOSE`
            - size (str): 注文数量
            - price (str): 注文価格
            - status (str): 注文ステータス: `ORDERED` `MODIFYING` `EXECUTED` `EXPIRED`
            - cancelType (str): 取消区分: `OCO` ※statusがEXPIREDの場合のみ返却
            - expiry (str): 注文有効期限
            - timestamp (str): 注文日時

        Examples:
        ```
        [
          {
            "rootOrderId": 123456789,
            "clientOrderId": "abc123",
            "orderId": 123456789,
            "symbol": "USD_JPY",
            "side": "BUY",
            "orderType": "OCO",
            "executionType": "LIMIT",
            "settleType": "OPEN",
            "size": "10000",
            "price": "140.525",
            "status": "EXECUTED",
            "expiry" : "20190418",
            "timestamp": "2019-03-19T02:15:06.059Z"
          },
          {
            "rootOrderId": 123456789,
            "clientOrderId": "abc123",
            "orderId": 123456790,
            "symbol": "USD_JPY",
            "side": "BUY",
            "orderType": "OCO",
            "executionType": "STOP",
            "settleType": "OPEN",
            "size": "10000",
            "price": "145.607",
            "status": "EXPIRED",
            "cancelType": "OCO",
            "expiry" : "20190418",
            "timestamp": "2019-03-19T02:15:06.059Z"
          }
        ]
        ```
        """
        await PrivateAPI.post_api_limiter()
        method = "POST"
        path = "/v1/changeOcoOrder"
        req_body = {}
        if rootOrderId and clientOrderId:
            raise ValueError("rootOrderId clientOrderId 2つ同時には設定できません。")
        elif rootOrderId:
            req_body["rootOrderId"] = rootOrderId
        elif clientOrderId:
            req_body["clientOrderId"] = clientOrderId
        else:
            raise ValueError("rootOrderId clientOrderId いずれか1つが必須です。")
        if limitPrice is None and stopPrice is None:
            raise ValueError("limitPrice stopPrice 両方もしくはどちらか1つが必須です。")
        if limitPrice:
            req_body["limitPrice"] = limitPrice
        if stopPrice:
            req_body["stopPrice"] = stopPrice
        headers = self._generate_headers(method, path, req_body)
        response = await self._request(method, path, headers=headers, req_body=req_body)
        return response.get("data", [])

    async def change_ifd_order(
        self,
        rootOrderId: int | None = None,
        clientOrderId: str | None = None,
        firstPrice: str | None = None,
        secondPrice: str | None = None,
    ) -> list:
        """IFD注文変更をします。rootOrderId clientOrderId いずれか1つが必須です。2つ同時には設定できません。firstPrice secondPrice 両方もしくはどちらか1つが必須です。

        Args:
            rootOrderId (int, optional): 親注文ID
            clientOrderId (str, optional): 顧客注文ID ※36文字以内の半角英数字の組合わせのみ使用可能
            firstPrice (str, optional): 1次注文レート
            secondPrice (str, optional): 2次注文レート

        Raises:
            ValueError: rootOrderId clientOrderId 2つ同時には設定できません。
            ValueError: rootOrderId clientOrderId いずれか1つが必須です。
            ValueError: firstPrice secondPrice 両方もしくはどちらか1つが必須です。

        Returns:
            list: 注文情報のリスト
            - rootOrderId (int): 親注文ID
            - clientOrderId (str): 顧客注文ID ※設定した場合のみ返却
            - orderId (int): 注文ID
            - symbol (str): 銘柄名
            - side (str): 売買区分: `BUY` `SELL`
            - orderType (str): 取引区分: `IFD`
            - executionType (str): 注文タイプ: `LIMIT` `STOP`
            - settleType (str): 決済区分: `OPEN` `CLOSE`
            - size (str): 注文数量
            - price (str): 注文価格
            - status (str): 注文ステータス: `WAITING` `ORDERED` `MODIFYING` `EXECUTED`
            - expiry (str): 注文有効期限
            - timestamp (str): 注文日時

        Examples:
        ```
        [
          {
            "rootOrderId": 123456789,
            "clientOrderId": "abc123",
            "orderId": 123456789,
            "symbol": "USD_JPY",
            "side": "BUY",
            "orderType": "IFD",
            "executionType": "LIMIT",
            "settleType": "OPEN",
            "size": "10000",
            "price": "136.201",
            "status": "ORDERED",
            "expiry" : "20190418",
            "timestamp": "2019-03-19T02:15:06.059Z"
          },
          {
            "rootOrderId": 123456789,
            "clientOrderId": "abc123",
            "orderId": 123456790,
            "symbol": "USD_JPY",
            "side": "SELL",
            "orderType": "IFD",
            "executionType": "LIMIT",
            "settleType": "CLOSE",
            "size": "10000",
            "price": "139.802",
            "status": "WAITING",
            "expiry" : "20190418",
            "timestamp": "2019-03-19T02:15:06.059Z"
          }
        ]
        ```
        """
        await PrivateAPI.post_api_limiter()
        method = "POST"
        path = "/v1/changeIfdOrder"
        req_body = {}
        if rootOrderId and clientOrderId:
            raise ValueError("rootOrderId clientOrderId 2つ同時には設定できません。")
        elif rootOrderId:
            req_body["rootOrderId"] = rootOrderId
        elif clientOrderId:
            req_body["clientOrderId"] = clientOrderId
        else:
            raise ValueError("rootOrderId clientOrderId いずれか1つが必須です。")
        if firstPrice is None and secondPrice is None:
            raise ValueError("firstPrice secondPrice 両方もしくはどちらか1つが必須です。")
        if firstPrice:
            req_body["firstPrice"] = firstPrice
        if secondPrice:
            req_body["secondPrice"] = secondPrice
        headers = self._generate_headers(method, path, req_body)
        response = await self._request(method, path, headers=headers, req_body=req_body)
        return response.get("data", [])

    async def change_ifo_order(
        self,
        rootOrderId: int | None = None,
        clientOrderId: str | None = None,
        firstPrice: str | None = None,
        secondLimitPrice: str | None = None,
        secondStopPrice: str | None = None,
    ) -> list:
        """IFDOCO注文変更をします。rootOrderId clientOrderId いずれか1つが必須です。2つ同時には設定できません。firstPrice secondLimitPrice secondStopPrice の内全てもしくはいずれか1つ以上が必須です。

        Args:
            rootOrderId (int, optional): 親注文ID
            clientOrderId (str, optional): 顧客注文ID ※36文字以内の半角英数字の組合わせのみ使用可能
            firstPrice (str, optional): 1次注文レート
            secondLimitPrice (str, optional): 2次指値注文レート
            secondStopPrice (str, optional): 2次逆指値注文レート

        Raises:
            ValueError: rootOrderId clientOrderId 2つ同時には設定できません。
            ValueError: rootOrderId clientOrderId いずれか1つが必須です。
            ValueError: firstPrice secondLimitPrice secondStopPrice の内全てもしくはいずれか1つ以上が必須です。

        Returns:
            list: 注文情報のリスト
            - rootOrderId (int): 親注文ID
            - clientOrderId (str): 顧客注文ID ※設定した場合のみ返却
            - orderId (int): 注文ID
            - symbol (str): 銘柄名
            - side (str): 売買区分: `BUY` `SELL`
            - orderType (str): 取引区分: `IFDOCO`
            - executionType (str): 注文タイプ: `LIMIT` `STOP`
            - settleType (str): 決済区分: `OPEN` `CLOSE`
            - size (str): 注文数量
            - price (str): 注文価格
            - status (str): 注文ステータス: `WAITING` `ORDERED` `MODIFYING` `EXECUTED` `EXPIRED`
            - cancelType (str): 取消区分: `OCO`
            - expiry (str): 注文有効期限
            - timestamp (str): 注文日時

        Examples:
        ```
        [
          {
            "rootOrderId": 123456789,
            "clientOrderId": "abc123",
            "orderId": 123456789,
            "symbol": "USD_JPY",
            "side": "SELL",
            "orderType": "IFDOCO",
            "executionType": "LIMIT",
            "settleType": "OPEN",
            "size": "10000",
            "price": "142.3",
            "status": "ORDERED",
            "expiry" : "20190418",
            "timestamp": "2019-03-19T02:15:06.059Z"
          },
          {
            "rootOrderId": 123456789,
            "clientOrderId": "abc123",
            "orderId": 123456790,
            "symbol": "USD_JPY",
            "side": "BUY",
            "orderType": "IFDOCO",
            "executionType": "LIMIT",
            "settleType": "CLOSE",
            "size": "10000",
            "price": "136",
            "status": "WAITING",
            "expiry" : "20190418",
            "timestamp": "2019-03-19T02:15:06.059Z"
          },
          {
            "rootOrderId": 123456789,
            "clientOrderId": "abc123",
            "orderId": 123456791,
            "symbol": "USD_JPY",
            "side": "BUY",
            "orderType": "IFDOCO",
            "executionType": "STOP",
            "settleType": "CLOSE",
            "size": "10000",
            "price": "143.1",
            "status": "WAITING",
            "expiry" : "20190418",
            "timestamp": "2019-03-19T02:15:06.059Z"
          }
        ]
        ```
        """
        await PrivateAPI.post_api_limiter()
        method = "POST"
        path = "/v1/changeIfoOrder"
        req_body = {}

        if rootOrderId and clientOrderId:
            raise ValueError("rootOrderId clientOrderId 2つ同時には設定できません。")
        elif rootOrderId:
            req_body["rootOrderId"] = rootOrderId
        elif clientOrderId:
            req_body["clientOrderId"] = clientOrderId
        else:
            raise ValueError("rootOrderId clientOrderId いずれか1つが必須です。")
        if firstPrice is None and secondLimitPrice is None and secondStopPrice is None:
            raise ValueError("firstPrice secondLimitPrice secondStopPrice の内全てもしくはいずれか1つ以上が必須です。")
        if firstPrice:
            req_body["firstPrice"] = firstPrice
        if secondLimitPrice:
            req_body["secondLimitPrice"] = secondLimitPrice
        if secondStopPrice:
            req_body["secondStopPrice"] = secondStopPrice
        headers = self._generate_headers(method, path, req_body)
        response = await self._request(method, path, headers=headers, req_body=req_body)
        return response.get("data", [])

    async def cancel_orders(
        self, rootOrderIds: list[str] | None = None, clientOrderIds: list[str] | None = None
    ) -> list:
        """複数の注文を取消します。rootOrderIds clientOrderIds いずれか1つが必須です。2つ同時には設定できません。最大10件まで注文を取消することができます。

        Args:
            rootOrderIds (list[str], optional): 親注文IDのリスト
            clientOrderIds (list[str], optional): 顧客注文IDのリスト

        Raises:
            ValueError: rootOrderIds clientOrderIds 2つ同時には設定できません。
            ValueError: rootOrderIds clientOrderIds いずれか1つが必須です。

        Returns:
            list: 取消受付に成功した親注文IDと顧客注文ID ※顧客注文IDは設定した場合のみ返却

        Examples:
        ```
        [
          {
            "clientOrderId": "abc123",
            "rootOrderId": 123456789
          },
          {
            "rootOrderId": 223456789
          }
        ]
        ```
        """
        await PrivateAPI.post_api_limiter()
        method = "POST"
        path = "/v1/cancelOrders"
        req_body = {}
        if rootOrderIds and clientOrderIds:
            raise ValueError("rootOrderIds clientOrderIds 2つ同時には設定できません。")
        elif rootOrderIds:
            req_body["rootOrderIds"] = rootOrderIds
        elif clientOrderIds:
            req_body["clientOrderIds"] = clientOrderIds
        else:
            raise ValueError("rootOrderIds clientOrderIds いずれか1つが必須です。")
        headers = self._generate_headers(method, path, req_body)
        response = await self._request(method, path, headers=headers, req_body=req_body)
        data: dict = response.get("data", {})
        return data.get("success", [])

    async def cancel_bulk_order(
        self, symbols: list[str], side: str | None = None, settleType: str | None = None
    ) -> list:
        """一括で注文(通常注文、特殊注文いずれも)を取消します。取消対象検索後に、対象注文を全て取消します。1次注文が約定していないIFD、IFDOCOケースでは1次注文もしくは2次注文にsideとsettleTypeの両方が一致するものが1つでもあれば注文全体を取消します。1次注文が約定しているIFD、IFDOCOケースでは2次注文にsideとsettleTypeの両方が一致するものがあれば2次注文を取消します。

        Args:
            symbols (list[str]): 銘柄名のリスト
            side (str, optional): 売買区分 `BUY` `SELL` ※指定時のみ指定された売買区分の注文を取消条件に追加
            settleType (str, optional): 決済区分 `OPEN` `CLOSE` ※指定時のみ指定された決済区分の注文を取消条件に追加

        Returns:
            list: 取消受付に成功した親注文IDと顧客注文ID ※顧客注文IDは設定した場合のみ返却

        Examples:
        ```
        [
          {
            "clientOrderId": "abc123",
            "rootOrderId": 123456789
          },
          {
            "rootOrderId": 223456789
          }
        ]
        ```
        """
        await PrivateAPI.post_api_limiter()
        method = "POST"
        path = "/v1/cancelBulkOrder"
        req_body: dict[str, list[str] | str] = {"symbols": symbols}
        if side:
            req_body["side"] = side
        if settleType:
            req_body["settleType"] = settleType
        headers = self._generate_headers(method, path, req_body)
        response = await self._request(method, path, headers=headers, req_body=req_body)
        data: dict = response.get("data", {})
        return data.get("success", [])

    async def close_order(
        self,
        symbol: str,
        side: str,
        executionType: str,
        clientOrderId: str | None = None,
        size: str | None = None,
        limitPrice: str | None = None,
        stopPrice: str | None = None,
        lowerBound: str | None = None,
        upperBound: str | None = None,
        settlePosition: list[dict] | None = None,
    ) -> list:
        """決済注文をします。size settlePosition いずれか1つが必須です。2つ同時には設定できません。

        Args:
            symbol (str): 銘柄名
            side (str): 売買区分 `BUY` `SELL`
            executionType (str): 注文種別 `MARKET` `LIMIT` `STOP` `OCO`
            clientOrderId (str, optional): 顧客注文ID ※36文字以内の半角英数字の組合わせのみ使用可能
            size (str, optional): 注文数量
            limitPrice (str, optional): 指値注文レート
            stopPrice (str, optional): 逆指値注文レート
            lowerBound (str, optional): 成立下限価格
            upperBound (str, optional): 成立上限価格
            settlePosition (list[dict], optional): 複数建玉 複数指定可能

        Raises:
            ValueError: size settlePosition 2つ同時には設定できません。
            ValueError: size settlePosition いずれか1つが必須です。
            ValueError: limitPrice は注文タイプが LIMIT または OCO の場合に必須です。
            ValueError: stopPrice は注文タイプが STOP または OCO の場合に必須です。

        Returns:
            list: 決済注文情報のリスト
            - rootOrderId (int): 親注文ID
            - clientOrderId (str): 顧客注文ID ※設定した場合のみ返却
            - orderId (int): 注文ID
            - symbol (str): 銘柄名
            - side (str): 売買区分: `BUY` `SELL`
            - orderType (str): 取引区分: `NORMAL` `OCO`
            - executionType (str): 注文タイプ: `MARKET` `LIMIT` `STOP`
            - settleType (str): 決済区分: `CLOSE`
            - size (str): 注文数量
            - price (str): 注文価格 ※`LIMIT` `STOP`の場合のみ返却
            - status (str): 注文ステータス: `WAITING` `EXECUTED` `EXPIRED`
            - cancelType (str): 取消区分: `PRICE_BOUND` `OCO` ※statusが`EXPIRED`の場合のみ返却
            - expiry (str): 注文有効期限
            - timestamp (str): 注文日時

        Examples:
        ```
        [
          {
            "rootOrderId": 123456789,
            "clientOrderId": "abc123",
            "orderId": 123456789,
            "symbol": "USD_JPY",
            "side": "BUY",
            "orderType": "NORMAL",
            "executionType": "LIMIT",
            "settleType": "CLOSE",
            "size": "10000",
            "price": "135.5",
            "status": "WAITING",
            "expiry": "20230418",
            "timestamp": "2019-03-19T01:07:24.467Z"
          }
        ]
        ```
        """
        await PrivateAPI.post_api_limiter()
        method = "POST"
        path = "/v1/closeOrder"
        req_body: dict[str, str | list[dict]] = {
            "symbol": symbol,
            "side": side,
            "executionType": executionType,
        }
        if size and settlePosition:
            raise ValueError("size settlePosition 2つ同時には設定できません。")
        elif size:
            req_body["size"] = size
        elif settlePosition:
            req_body["settlePosition"] = settlePosition
        else:
            raise ValueError("size settlePosition いずれか1つが必須です。")
        if clientOrderId:
            req_body["clientOrderId"] = clientOrderId
        if executionType == "LIMIT" or executionType == "OCO":
            if limitPrice is None:
                raise ValueError("limitPrice は注文タイプが LIMIT または OCO の場合に必須です。")
            req_body["limitPrice"] = limitPrice
        if executionType == "STOP" or executionType == "OCO":
            if stopPrice is None:
                raise ValueError("stopPrice は注文タイプが STOP または OCO の場合に必須です。")
            req_body["stopPrice"] = stopPrice
        if executionType == "MARKET":
            if side == "SELL" and lowerBound:
                req_body["lowerBound"] = lowerBound
            elif side == "BUY" and upperBound:
                req_body["upperBound"] = upperBound
        headers = self._generate_headers(method, path, req_body)
        response = await self._request(method, path, headers=headers, req_body=req_body)
        return response.get("data", [])

    ##### WebSocket Token API #####
    async def get_ws_token(self) -> str:
        """Private WebSocket API用のアクセストークンを取得します。有効期限は60分です。アクセストークンは最大5個まで発行できます。発行上限を超えた場合、有効期限の近いトークンから順に削除されます。発行済みのAPIキーを使ってアクセストークンを取得する場合、【会員ページ】-【API】-【編集】-【APIキーの編集】画面で「約定情報通知(WebSocket)」、「注文情報通知(WebSocket)」、「ポジション情報通知(WebSocket)」または「ポジションサマリー情報通知(WebSocket)」にチェックを入れてから、アクセストークンを取得します。※APIキーの権限を編集する前に取得したアクセストークンには、編集後の権限設定は反映されませんので、ご注意ください。

        Returns:
            str: アクセストークン

        Examples:
        ```
        "xxxxxxxxxxxxxxxxxxxx"
        ```
        """
        await PrivateAPI.post_api_limiter()
        method = "POST"
        path = "/v1/ws-auth"
        req_body = {}
        headers = self._generate_headers(method, path, req_body)
        response = await self._request(method, path, headers=headers, req_body=req_body)
        return response.get("data", "")

    async def extend_ws_token(self, token: str) -> dict:
        """Private WebSocket API用のアクセストークンを延長します。延長前の残り有効期限に関わらず、新しい有効期限は60分となります。

        Args:
            token (str): アクセストークン

        Returns:
            dict: ステータス・レスポンスタイム

        Examples:
        ```
        {
          "status": 0,
          "responsetime": "2019-03-19T02:15:06.102Z"
        }
        ```
        """
        await PrivateAPI.post_api_limiter()
        method = "PUT"
        path = "/v1/ws-auth"
        req_body = {"token": token}
        headers = self._generate_headers(method, path, req_body)
        response = await self._request(method, path, headers=headers, req_body=req_body)
        return response

    async def delete_ws_token(self, token: str) -> dict:
        """Private WebSocket API用のアクセストークンを削除します。

        Args:
            token (str): アクセストークン

        Returns:
            dict: ステータス・レスポンスタイム

        Examples:
        ```
        {
          "status": 0,
          "responsetime": "2019-03-19T02:15:06.102Z"
        }
        ```
        """
        await PrivateAPI.post_api_limiter()
        method = "DELETE"
        path = "/v1/ws-auth"
        req_body = {"token": token}
        headers = self._generate_headers(method, path, req_body)
        response = await self._request(method, path, headers=headers, req_body=req_body)
        return response
