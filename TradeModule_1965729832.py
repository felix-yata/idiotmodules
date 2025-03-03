from .. import loader, utils
import asyncio
import re

class TradeModule(loader.Module):
    """Модуль для автоматизации торговли"""
    strings = {"name": "TradeModule"}

    async def client_ready(self, client, db):
        self.client = client
        self.running = False

    async def tradecmd(self, message):
        """Запускает торговый процесс"""
        self.running = True
        target_user_id = 5443619563
        await message.edit("🏁 Торговля запущена.")
        while self.running:
            response = await self.wait_for_response(target_user_id)
            if response:
                min_sell, max_buy = await self.parse_exchange(response)
                if min_sell is not None and max_buy is not None:
                    if min_sell - max_buy < 0.02:
                        await asyncio.sleep(2.5)
                        await self.client.send_message(
                            target_user_id, f".Биржа продать 99999 {min_sell:.2f}")
                        await asyncio.sleep(2.5)
                        await self.client.send_message(
                            target_user_id, f".Биржа купить 99999 {max_buy + 0.01:.2f}")
                    if min_sell - max_buy < 0.03:
                        await asyncio.sleep(2.5)
                        await self.client.send_message(
                            target_user_id, f".Биржа продать 99999 {min_sell:.2f}")
                        await asyncio.sleep(2.5)
                        await self.client.send_message(
                            target_user_id, f".Биржа купить 99999 {max_buy + 0.01:.2f}")
                    else:
                        await asyncio.sleep(2.5)
                        await self.client.send_message(
                            target_user_id, f".Биржа продать 99999 {min_sell - 0.01:.2f}")
                        await asyncio.sleep(2.5)
                        await self.client.send_message(
                            target_user_id, f".Биржа купить 99999 {max_buy + 0.01:.2f}")
                else:
                    await message.respond("⚠️ Не удалось получить данные о ценах.")
            else:
                await message.respond("⚠️ Не получен ответ от биржи.")
            await asyncio.sleep(600)
    async def purcmd(self, message):
        """Покупает по максимальной цене покупки"""
        target_user_id = 5443619563
        await message.edit("🤑 Ща куплю")
        response = await self.wait_for_response(target_user_id)
        if response:
            min_sell, max_buy = await self.parse_exchange(response)
            if min_sell is not None and max_buy is not None:
                if min_sell - max_buy < 0.02:
                    await asyncio.sleep(2.5)
                    await self.client.send_message(
                        target_user_id, f".Биржа купить 9999 {max_buy}")
                else:
                    await asyncio.sleep(2.5)
                    await self.client.send_message(
                        target_user_id, f".Биржа купить 9999 {max_buy + 0.01:.2f}")
            else:
                await message.respond("⚠️ Не удалось получить данные о ценах.")
        else:
            await message.respond("⚠️ Не получен ответ от биржи.")
    async def sellcmd(self, message):
        """Продает по минимальной цене продажи"""
        target_user_id = 5443619563
        await message.edit("🤑 Ща продам")
        response = await self.wait_for_response(target_user_id)
        if response:
            min_sell, max_buy = await self.parse_exchange(response)
            if min_sell is not None and max_buy is not None:
                if min_sell - max_buy < 0.02:
                    await asyncio.sleep(2.5)
                    await self.client.send_message(
                        target_user_id, f".Биржа продать 9999 {min_sell}")
                else:
                    await asyncio.sleep(2.5)
                    await self.client.send_message(
                        target_user_id, f".Биржа продать 9999 {min_sell - 0.01:.2f}")
            else:
                await message.respond("⚠️ Не получен ответ от биржи.")
            await asyncio.sleep(54)
    async def stoptradecmd(self, message):
        """Останавливает торговый процесс"""
        target_user_id = 2314759542
        await self.client.send_message(target_user_id, ".Биржа отмена все")
        self.running = False
        await message.edit("🛑 Торговля остановлена.")

    async def parse_exchange(self, message):
        text = message.message
        text = text.replace(',', '.').replace('\xa0', ' ')
        sell_section = re.search(r"🔽 Заявки на продажу([\s\S]*?)🔼 Заявки на покупку", text)
        buy_section = re.search(r"🔼 Заявки на покупку([\s\S]*)", text)

        min_sell = None
        max_buy = None

        if sell_section:
            sell_prices = re.findall(r"(\d+\.\d+) ирисок", sell_section.group(1))
            sell_prices = [float(price) for price in sell_prices]
            if sell_prices:
                min_sell = min(sell_prices)

        if buy_section:
            buy_prices = re.findall(r"(\d+\.\d+) ирисок", buy_section.group(1))
            buy_prices = [float(price) for price in buy_prices]
            if buy_prices:
                max_buy = max(buy_prices)

        return min_sell, max_buy

    async def wait_for_response(self, user_id):
        try:
            async with self.client.conversation(user_id, timeout=30) as conv:
                await conv.send_message("Биржа отмена все")
                await asyncio.sleep(2.5)
                await conv.send_message("биржа")
                response = await conv.get_response()
                return response
        except asyncio.TimeoutError:
            return None
