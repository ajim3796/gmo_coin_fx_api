# gmo-coin-fx-api

GMOコインの外国為替FX APIクライアントライブラリです。

## 概要

このライブラリは、GMOコインが提供する外国為替FXの公開APIおよびプライベートAPIを簡単に利用するためのPythonクライアントです。

## 機能一覧

各APIの詳細な関数一覧と概要については<a href="FUNCTION_SUMMARY.md" target="_blank">こちら</a>をご覧ください。

GMOコインFX APIの公式ドキュメントは<a href="https://api.coin.z.com/fxdocs/?python#outline" target="_blank">こちら</a>です。

## 基本的な使い方 (利用例)

- PublicAPI

```python
import asyncio

from gmo_coin_fx_api import PublicAPI


async def main():
    """
    非同期でPublic APIを呼び出すメイン関数
    """
    # async with を使って安全にAPIクライアントを初期化
    async with PublicAPI() as public_api:
        try:
            status = await public_api.get_status()
            print(status)
        except Exception as e:
            print(f"エラーが発生しました: {e}")


if __name__ == "__main__":
    asyncio.run(main())
```

- PrivateAPI

```python
import asyncio

from gmo_coin_fx_api import PrivateAPI

api_key = "YOUR_API_KEY"
secret_key = "YOUR_API_SECRET"


async def main():
    """
    非同期でPrivate APIを呼び出すメイン関数
    """
    # async with を使って安全にAPIクライアントを初期化
    async with PrivateAPI(api_key, secret_key) as private_api:
        try:
            assets = await private_api.get_assets()
            print(assets)
        except Exception as e:
            print(f"エラーが発生しました: {e}")


if __name__ == "__main__":
    asyncio.run(main())
```

**注:** 上記のコードは利用例です。実際のAPI仕様やライブラリの実装に合わせてメソッドを呼び出してください。

## 開発

### セットアップ

このプロジェクトでは `uv` を利用しています。リポジトリをクローンした後、以下のコマンドで開発環境をセットアップできます。

```bash
uv sync -U
```

## 作者

- ajim
