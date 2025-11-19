import asyncio


class RateLimiter:
    def __init__(self, max_calls, period) -> None:
        self.max_calls = max_calls
        self.period = period
        self.calls = []

    async def __call__(self) -> None:
        now = asyncio.get_running_loop().time()
        self.calls = [call for call in self.calls if call > now - self.period]
        if len(self.calls) >= self.max_calls:
            sleep_time = self.period - (now - self.calls[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            self.calls.append(asyncio.get_running_loop().time())
        else:
            self.calls.append(asyncio.get_running_loop().time())
