import logging
import random
import time
import json
import re
import pymorphy2
from .. import loader, utils
from telethon import types

logger = logging.getLogger(__name__)

def serialize_messages(messages):
    serialized = {}
    for key, value in messages.items():
        new_key = '|||'.join(key) if isinstance(key, tuple) else key
        serialized[new_key] = value
    return json.dumps(serialized, ensure_ascii=False)

def deserialize_messages(s):
    messages = {}
    if s:
        serialized = json.loads(s)
        for key, value in serialized.items():
            new_key = tuple(key.split('|||')) if '|||' in key else (key,)
            messages[new_key] = value
    return messages

def serialize_dict(d):
    return json.dumps(d, ensure_ascii=False)

def deserialize_dict(s):
    try:
        return json.loads(s) if s else {}
    except:
        return {}

@loader.tds
class MarkovChainMod(loader.Module):
    strings = {
        "name": "MarkovChain",
        "pref": "[MarkovChain] ",
        "need_arg": "{}Нужен аргумент",
        "status": "{}{}",
        "on": "{}Включён",
        "off": "{}Выключен",
    }
    _db_name = "MarkovChain"

    async def client_ready(self, _, db):
        self.db = db
        self.morph = pymorphy2.MorphAnalyzer()
        self._chats = self.db.get(self._db_name, "chats", [])
        self._messages = deserialize_messages(self.db.get(self._db_name, "messages_data", ""))
        self._context = deserialize_dict(self.db.get(self._db_name, "context_data", ""))
        self._word_stats = deserialize_dict(self.db.get(self._db_name, "word_stats_data", ""))
        self._learned_triggers = deserialize_dict(self.db.get(self._db_name, "learned_triggers_data", ""))
        self._media_storage = deserialize_dict(self.db.get(self._db_name, "media_storage", ""))
        self._base_triggers = {
            'positive': ['круто', 'класс', 'ок', 'окей', 'хорошо'],
            'negative': ['плохо', 'ужас', 'фу', 'мда', 'так себе'],
            'love': ['люблю', 'обожаю', 'нравится'],
            'hate': ['ненавижу', 'не нравится', 'раздражает']
        }
        if not self.db.get(self._db_name, "chance"):
            self.db.set(self._db_name, "chance", 2)
        self.convert_message_keys()

    def convert_message_keys(self):
        new_messages = {}
        for key, value in self._messages.items():
            key_str = '|||'.join(key) if isinstance(key, tuple) else key
            new_messages[key_str] = value
        self._messages = new_messages

    def _save_data(self):
        self.db.set(self._db_name, "messages_data", serialize_messages(self._messages))
        self.db.set(self._db_name, "context_data", serialize_dict(self._context))
        self.db.set(self._db_name, "word_stats_data", serialize_dict(self._word_stats))
        self.db.set(self._db_name, "learned_triggers_data", serialize_dict(self._learned_triggers))
        self.db.set(self._db_name, "media_storage", serialize_dict(self._media_storage))
        self.db.set(self._db_name, "chats", self._chats)

    @staticmethod
    def str2bool(v):
        return v.lower() in ("yes", "y", "true", "on", "да")

    async def markovcmd(self, m: types.Message):
        """Переключить режим генерации текста"""
        args = utils.get_args_raw(m)
        if not m.chat:
            return
        chat = m.chat.id
        if self.str2bool(args):
            if chat not in self._chats:
                self._chats.append(chat)
                self._save_data()
            return await utils.answer(m, self.strings("on").format(self.strings("pref")))
        if chat in self._chats:
            self._chats.remove(chat)
            self._save_data()
        return await utils.answer(m, self.strings("off").format(self.strings("pref")))

    async def mkchancecmd(self, message):
        """[число N] - установить шанс ответа 1 к N (0 - отвечаю всегда)"""
        args = utils.get_args_raw(message)
        if not args:
            current = self.db.get(self._db_name, "chance", 2)
            if current == 0:
                return await message.edit(f"{self.strings('pref')}Текущий режим: отвечаю всегда")
            return await message.edit(f"{self.strings('pref')}Текущий шанс: 1 к {current}")
        try:
            chance = int(args)
            if chance < 0:
                return await message.edit(f"{self.strings('pref')}Число должно быть >= 0")
            self.db.set(self._db_name, "chance", chance)
            if chance == 0:
                await message.edit(f"{self.strings('pref')}Установлен режим: отвечаю всегда")
            else:
                await message.edit(f"{self.strings('pref')}Установлен шанс: 1 к {chance}")
        except ValueError:
            await message.edit(f"{self.strings('pref')}Введите целое число")

    def clean_text(self, text):
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        words = text.split()
        return words

    def lemmatize_words(self, words):
        return [self.morph.parse(word)[0].normal_form for word in words]

    def analyze_message(self, text):
        words = self.clean_text(text)
        words = self.lemmatize_words(words)
        for word in words:
            self._word_stats[word] = self._word_stats.get(word, 0) + 1
        for i, word in enumerate(words):
            context = words[max(0, i-2):min(len(words), i+3)]
            for mood, trigger_words in self._base_triggers.items():
                if any(t in context for t in trigger_words):
                    if self._word_stats.get(word, 0) > 10:
                        if mood not in self._learned_triggers:
                            self._learned_triggers[mood] = []
                        if word not in self._learned_triggers[mood]:
                            self._learned_triggers[mood].append(word)
        mood = 'neutral'
        all_triggers = self._base_triggers.copy()
        for m, trigger_list in self._learned_triggers.items():
            if m not in all_triggers:
                all_triggers[m] = []
            all_triggers[m].extend(trigger_list)
        for m, trigger_words in all_triggers.items():
            if any(word in trigger_words for word in words):
                mood = m
                break
        self._save_data()
        return mood

    async def mktriggerscmd(self, message):
        """Показать выученные триггерные слова"""
        text = "📝 Триггерные слова:\n\n"
        text += "Базовые:\n"
        for mood, words in self._base_triggers.items():
            text += f"• {mood}: {', '.join(words)}\n"
        text += "\nВыученные:\n"
        for mood, words in self._learned_triggers.items():
            if words:
                text += f"• {mood}: {', '.join(words)}\n"
        await message.edit(text)

    async def watcher(self, m: types.Message):
        if not isinstance(m, types.Message):
            return
        if m.sender_id == (await m.client.get_me()).id or not m.chat:
            return
        if m.chat.id not in self._chats:
            return
        chance = self.db.get(self._db_name, "chance", 2)
        if chance != 0 and random.randint(1, chance) != 1:
            return
        chat_id = str(m.chat.id)
        if m.media:
            if chat_id not in self._media_storage:
                self._media_storage[chat_id] = []
            media_type = self.get_media_type(m)
            self._media_storage[chat_id].append({
                'msg_id': m.id,
                'type': media_type,
                'time': time.time()
            })
            if len(self._media_storage[chat_id]) > 100:
                self._media_storage[chat_id] = self._media_storage[chat_id][-100:]
        mood = self.analyze_message(m.raw_text)
        self.add_message_to_chain(m.chat.id, m.raw_text, mood)
        # Adjusted chance: lower probability for media messages
        if random.randint(1, 4) == 1:  # 25% chance to send media
            if self._media_storage.get(chat_id):
                media = random.choice(self._media_storage[chat_id])
                try:
                    await m.client.send_message(m.chat.id, file=await m.client.get_messages(m.chat.id, ids=media['msg_id']))
                except:
                    generated_message = self.generate_message(m.chat.id)
                    if generated_message:
                        await m.reply(generated_message)
            else:
                generated_message = self.generate_message(m.chat.id)
                if generated_message:
                    await m.reply(generated_message)
        else:
            generated_message = self.generate_message(m.chat.id)
            if generated_message:
                await m.reply(generated_message)
        self._save_data()

    def get_media_type(self, message):
        if message.photo:
            return 'photo'
        elif message.sticker:
            return 'sticker'
        elif message.voice:
            return 'voice'
        elif message.video:
            return 'video'
        elif message.video_note:
            return 'video_note'
        elif message.gif or (message.document and getattr(message.document, 'mime_type', '').startswith('video')):
            return 'gif'
        else:
            return 'other'

    def add_message_to_chain(self, chat_id, message, mood='neutral'):
        words = self.clean_text(message)
        words = self.lemmatize_words(words)
        for n in range(2, 4):
            if len(words) < n:
                continue
            for i in range(len(words) - n + 1):
                key = tuple(words[i:i + n - 1])
                key_str = '|||'.join(key)
                next_word = words[i + n - 1]
                if key_str not in self._messages:
                    self._messages[key_str] = []
                self._messages[key_str].append(next_word)
                if len(self._messages[key_str]) > 1000:
                    self._messages[key_str] = self._messages[key_str][-1000:]
        if str(chat_id) not in self._context:
            self._context[str(chat_id)] = []
        self._context[str(chat_id)].append({
            'text': message,
            'mood': mood,
            'time': time.time()
        })
        if len(self._context[str(chat_id)]) > 500:
            self._context[str(chat_id)] = self._context[str(chat_id)][-500:]
        self._save_data()

    def generate_message(self, chat_id):
        if not self._messages:
            return None
        context = self._context.get(str(chat_id), [])
        recent_words = []
        if context:
            last_messages = context[-5:]
            for msg in last_messages:
                words = self.clean_text(msg['text'])
                words = self.lemmatize_words(words)
                recent_words.extend(words)
            for n in range(2, 0, -1):
                if len(recent_words) >= n:
                    start_key = tuple(recent_words[-n:])
                    start_key_str = '|||'.join(start_key)
                    if start_key_str in self._messages:
                        break
            else:
                start_key_str = random.choice(list(self._messages.keys()))
        else:
            start_key_str = random.choice(list(self._messages.keys()))
        if isinstance(start_key_str, tuple):
            start_key_str = '|||'.join(start_key_str)
        start_key = start_key_str.split('|||')
        output = list(start_key)
        max_length = random.randint(3, 7)
        while len(output) < max_length:
            current_key = output[-(len(start_key)):]
            current_key_str = '|||'.join(current_key)
            next_words = self._messages.get(current_key_str)
            if not next_words:
                break
            word_counts = {}
            for word in next_words:
                word_counts[word] = word_counts.get(word, 0) + 1
            next_word = random.choices(
                list(word_counts.keys()),
                weights=list(word_counts.values())
            )[0]
            output.append(next_word)
        generated_text = ' '.join(output)
        return generated_text.strip()

    async def mkstatscmd(self, message):
        """Показать статистику обучения"""
        total_contexts = sum(len(ctx) for ctx in self._context.values())
        avg_chain = sum(len(v) for v in self._messages.values()) / len(self._messages) if self._messages else 0
        total_media = sum(len(media) for media in self._media_storage.values())
        stats = f"📊 Статистика обучения:\n"
        stats += f"• Изучено уникальных ключей: {len(self._messages)}\n"
        stats += f"• Сохранено контекстов: {total_contexts}\n"
        stats += f"• Выучено триггерных слов: {sum(len(words) for words in self._learned_triggers.values())}\n"
        stats += f"• Средняя длина цепочки: {avg_chain:.1f}\n"
        stats += f"• Сохранено медиа: {total_media}\n"
        await message.edit(stats)

    async def mkcleancmd(self, message):
        """Очистить старые данные"""
        for key in list(self._messages.keys()):
            if len(self._messages[key]) > 1000:
                self._messages[key] = self._messages[key][-1000:]
        current_time = time.time()
        for chat_id in self._media_storage:
            self._media_storage[chat_id] = [
                media for media in self._media_storage[chat_id]
                if current_time - media['time'] < 30 * 24 * 60 * 60
            ]
        self._save_data()
        await message.edit("Старые данные очищены")

    async def mkloadfilecmd(self, message):
        """.mkloadfile - загрузить данные для обучения из файла, отправленного в сообщении"""
        reply = await message.get_reply_message()
        if not reply or not reply.file:
            await message.edit("❗ Пожалуйста, ответьте на сообщение с текстовым файлом командой `.mkloadfile`.")
            return
        file = await reply.download_media(bytes)
        try:
            text = file.decode('utf-8', errors='ignore')
        except UnicodeDecodeError:
            await message.edit("❗ Не удалось декодировать файл. Убедитесь, что файл в формате UTF-8.")
            return
        lines = text.strip().split('\n')
        for line in lines:
            self.add_message_to_chain('external', line.strip())
        self._save_data()
        await message.edit("✅ Данные из файла успешно загружены и обработаны.")
        