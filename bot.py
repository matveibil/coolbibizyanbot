import os
import random
import logging
import time
import asyncio
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.request import HTTPXRequest

# Настройка логов
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

load_dotenv()
TOKEN = os.getenv("larp_token")

if not TOKEN:
    raise RuntimeError("❌ АШИПКА: Не задан larp_token в файле .env")

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "image")

WIN_IMAGE_PATH = os.path.join(BASE_DIR, "win.png")
LOSE_GIF_PATH = os.path.join(BASE_DIR, "lose.gif")
VOLCANO_IMAGE = os.path.join(BASE_DIR, "1000097590.jpg")
OLD_GOD_IMAGE = os.path.join(BASE_DIR, "old_god.jpg")

# --- СИСТЕМА РЕДКОСТЕЙ ---
RARITIES = {
    "Абычная 🐒": {"income": 1, "weight": 45, "images": ["1000097597.jpg", "1000097598.jpg", "1000097600.jpg", "1000097601.jpg", "normal.png"]},
    "Рицкая 🦧": {"income": 3, "weight": 30, "images": ["1000097589.jpg", "1000097593.jpg", "1000097594.jpg", "rare.png"]},
    "Эпик 👑": {"income": 10, "weight": 15, "images": ["1000097599.jpg", "1000097602.jpg", "epic.png"]},
    "Легенда 🚬": {"income": 30, "weight": 7, "images": ["1000097591.jpg", "1000097595.jpg"]},
    "Миф 🛸": {"income": 100, "weight": 2.9, "images": ["1000097592.jpg", "1000097596.jpg"]},
    "Батя Джунглей 🌋": {"income": 500, "weight": 0.1, "images": ["1000097590.jpg"]}
}

ACHIEVEMENTS = {
    "first_box": {"name": "📦 Первый шаг", "desc": "Открыть первое карыто", "reward": 50},
    "rich_1000": {"name": "💰 Первый миллионер", "desc": "Накопить 1000 бананов", "reward": 200},
    "killer_10": {"name": "🩸 Начало положено", "desc": "Победить в 10 битвах", "reward": 100},
    "boss_slayer": {"name": "🗡 Убийца Богов", "desc": "Победить Старого Бога", "reward": 500}
}

MONKEY_NEWS_IMAGES = [os.path.join(BASE_DIR, f"{i}.jpg") for i in range(1, 13)]
WAR_IMAGES = [os.path.join(BASE_DIR, "orig.jpg"), os.path.join(BASE_DIR, "orig (1).jpg"), os.path.join(BASE_DIR, "orig (2).jpg"), os.path.join(BASE_DIR, "orig (3).jpg")]
ATTACK_TYPES = ["Удар хвостом в табло 🦍", "Засада в лианах 🌿", "Банановая бомбежка 🍌", "Ночной махач 🌙", "Абезьяний крик 🗣", "Кидание какашек 💩", "Стырить бананы 🥷"]

NEWS_SUBJECTS = ["Дикая мартышка", "Горилла-качок", "Стая воробьев", "Пьяный тукан", "Бешеная белка", "Ктулху-Бибизяна"]
NEWS_ACTIONS = ["угнала трактор", "устроила дебош", "съела все запасы", "построила шалаш", "объявила войну муравьям", "открыла казино"]
NEWS_REASONS = ["чтобы купить VPN", "ради мемов", "потому что ей скучно", "чтобы захватить мир", "из-за спора на бананы"]

def generate_meme_news():
    return f"🤪 **МЕМ:** {random.choice(NEWS_SUBJECTS)} {random.choice(NEWS_ACTIONS)}, {random.choice(NEWS_REASONS)}!"

def build_game_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("Бежать до сваих"), KeyboardButton("Махаться с чужими")],
        [KeyboardButton("Вскрыть карыто (5 🍌)"), KeyboardButton("🎰 Слот-машина")],
        [KeyboardButton("🥷 Ограбить"), KeyboardButton("👹 Логово Босса")],
        [KeyboardButton("📰 Бибизяни новости"), KeyboardButton("🧬 Склещить бибизян")],
        [KeyboardButton("🏆 Вожаки стаи"), KeyboardButton("🌐 Оплатить связь (50 🍌)")],
        [KeyboardButton("Чо в кармане?")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def init_user_data(context: ContextTypes.DEFAULT_TYPE, user_id: int, user_name: str) -> None:
    if "bananas" not in context.user_data: context.user_data["bananas"] = 0
    if "monkeys" not in context.user_data: context.user_data["monkeys"] = {rarity: 0 for rarity in RARITIES.keys()}
    if "defeated" not in context.user_data: context.user_data["defeated"] = 0
    if "name" not in context.user_data: context.user_data["name"] = user_name
    if "last_internet_pay" not in context.user_data: context.user_data["last_internet_pay"] = 0
    if "achievements" not in context.user_data: context.user_data["achievements"] = []
    if "boxes_opened" not in context.user_data: context.user_data["boxes_opened"] = 0
    if "boss_hp" not in context.user_data: context.user_data["boss_hp"] = 0
    
    if "last_seen" not in context.user_data: context.user_data["last_seen"] = time.time()

    if "leaderboard" not in context.bot_data: context.bot_data["leaderboard"] = {}
    context.bot_data["leaderboard"][user_id] = {
        "name": context.user_data["name"],
        "bananas": context.user_data["bananas"],
        "defeated": context.user_data["defeated"]
    }

async def check_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    unlocked = context.user_data["achievements"]
    new_unlocks = []
    
    if "first_box" not in unlocked and context.user_data["boxes_opened"] >= 1:
        context.user_data["bananas"] += ACHIEVEMENTS["first_box"]["reward"]
        unlocked.append("first_box")
        new_unlocks.append(ACHIEVEMENTS["first_box"])
        
    if "rich_1000" not in unlocked and context.user_data["bananas"] >= 1000:
        context.user_data["bananas"] += ACHIEVEMENTS["rich_1000"]["reward"]
        unlocked.append("rich_1000")
        new_unlocks.append(ACHIEVEMENTS["rich_1000"])
        
    if "killer_10" not in unlocked and context.user_data["defeated"] >= 10:
        context.user_data["bananas"] += ACHIEVEMENTS["killer_10"]["reward"]
        unlocked.append("killer_10")
        new_unlocks.append(ACHIEVEMENTS["killer_10"])

    for ach in new_unlocks:
        await update.message.reply_text(f"🎖 **НОВОЕ ДОСТИЖЕНИЕ:** {ach['name']}!\n{ach['desc']}\n💰 Награда: +{ach['reward']} 🍌", parse_mode="Markdown")

async def passive_income_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    current_time = time.time()
    for user_id, user_data in context.application.user_data.items():
        if "monkeys" in user_data:
            last_pay = user_data.get("last_internet_pay", 0)
            internet_active = (current_time - last_pay) < 86400
            
            if not internet_active:
                try: await context.bot.send_message(chat_id=user_id, text="⚠️ **ИНТЕРНЕТ ОТКЛЮЧЕН!** Нажми «🌐 Оплатить связь (50 🍌)»!", parse_mode="Markdown")
                except: pass
                continue 

            monkeys = user_data["monkeys"]
            income = sum(monkeys.get(rarity, 0) * data["income"] for rarity, data in RARITIES.items())
            
            if income > 0:
                user_data["bananas"] = user_data.get("bananas", 0) + income
                try: await context.bot.send_message(chat_id=user_id, text=f"🏪 Бибизяны натаскали **+{income} 🍌**!", parse_mode="Markdown")
                except: pass
            
            # ВУЛКАН
            if random.random() < 0.01:
                if user_data.get("bananas", 0) > 0 or sum(monkeys.values()) > 0:
                    try:
                        with open(VOLCANO_IMAGE, "rb") as photo:
                            await context.bot.send_photo(chat_id=user_id, photo=photo, caption="🌋 **ВАХУН! ИЗВЕРЖЕНИЕ!**\nСмыло ВСЕ бананы и половину стаи!", parse_mode="Markdown")
                        user_data["bananas"] = 0
                        for rarity in monkeys: monkeys[rarity] = monkeys[rarity] // 2
                    except: pass
            
            # СТАРЫЙ БОГ
            elif random.random() < 0.005:
                user_data["bananas"] += 50
                try:
                    with open(OLD_GOD_IMAGE, "rb") as photo:
                        await context.bot.send_photo(chat_id=user_id, photo=photo, caption="🤣 **Старый бог упал с балкона!** Ты подобрал **+50 🍌**!", parse_mode="Markdown")
                except FileNotFoundError:
                    await context.bot.send_message(chat_id=user_id, text="🤣 **Старый бог упал с балкона!** Ты подобрал **+50 🍌**!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.effective_user.first_name or "Бибизяна"
    init_user_data(context, update.effective_user.id, user_name)
    
    now = time.time()
    last_seen = context.user_data.get("last_seen", now)
    time_offline = now - last_seen
    
    offline_msg = ""
    if time_offline > 60:
        time_offline = min(time_offline, 8 * 3600) # Макс 8 часов
        income = sum(context.user_data["monkeys"].get(r, 0) * d["income"] for r, d in RARITIES.items())
        earned = int(income * (time_offline / 60))
        if earned > 0:
            context.user_data["bananas"] += earned
            offline_msg = f"\n\n💤 **Пока тебя не было, бибизяны работали!**\nТы заработал: **+{earned} 🍌**"
    
    context.user_data["last_seen"] = now

    await update.message.reply_text(
        f"🍌 Уа-уа, **{user_name}**! Жми кнопки, чтобы лутать бананы!{offline_msg}\n\n⚠️ *Не забудь оплатить интернет!*",
        reply_markup=build_game_keyboard(), parse_mode="Markdown"
    )

async def handler_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text: return

    user_name = update.effective_user.first_name or "Бибизяна"
    init_user_data(context, update.effective_user.id, user_name)
    context.user_data["last_seen"] = time.time()
    text = update.message.text

    if text == "Бежать до сваих":
        is_win = random.choice([True, False])
        if is_win:
            context.user_data["bananas"] += 1
            try:
                with open(WIN_IMAGE_PATH, "rb") as photo_file:
                    await update.message.reply_photo(photo=photo_file, caption=f"ты дабежал да сваих\nБананов: {context.user_data['bananas']}")
            except FileNotFoundError: pass
        else:
            try:
                with open(LOSE_GIF_PATH, "rb") as gif_file:
                    await update.message.reply_animation(animation=gif_file, caption=f"ты пагиб🥀\nБананов: {context.user_data['bananas']}")
            except FileNotFoundError: pass
        await check_achievements(update, context)

    elif text == "🎰 Слот-машина":
        if context.user_data["bananas"] < 10:
            await update.message.reply_text("❌ Нужно 10 🍌 для игры!")
            return
        
        context.user_data["bananas"] -= 10
        context.user_data["casino_plays"] = context.user_data.get("casino_plays", 0) + 1
        
        msg = await update.message.reply_text("🎰 Крутим барабаны...\n[ 🍒 | 🍌 | 🍋 ]")
        await asyncio.sleep(1.5)
        await msg.edit_text("🎰 Крутим барабаны...\n[ 🍌 | 🍋 | 🍒 ]")
        await asyncio.sleep(1.5)
        
        roll = random.random()
        if roll < 0.45:
            context.user_data["bananas"] += 20
            await msg.edit_text(f"🎰 **ВЫИГРЫШ!** x2: **+20 🍌**!\nБаланс: {context.user_data['bananas']} 🍌\n[ 🍌 | 🍌 | 🍋 ]", parse_mode="Markdown")
        elif roll < 0.90:
            await msg.edit_text(f"🎰 **ПРОИГРЫШ.** Ты потерял 10 🍌.\nБаланс: {context.user_data['bananas']} 🍌\n[ 🍒 | 🍋 | 🍒 ]", parse_mode="Markdown")
        else:
            context.user_data["bananas"] += 50
            await msg.edit_text(f"💎 **ДЖЕКПОТ!!!** x5: **+50 🍌**!\nБаланс: {context.user_data['bananas']} 🍌\n[ 🍌 | 🍌 | 🍌 ]", parse_mode="Markdown")

    elif text == "🥷 Ограбить":
        # Ищем других игроков
        others = [uid for uid in context.bot_data["leaderboard"].keys() if uid != update.effective_user.id]
        if not others:
            await update.message.reply_text("В джунглях пока больше никого нет. Позови друзей или препода!")
            return
        
        victim_id = random.choice(others)
        victim_data = context.bot_data["leaderboard"][victim_id]
        
        if victim_data["bananas"] < 10:
            await update.message.reply_text(f"🥷 Ты нашел логово **{victim_data['name']}**, но у него меньше 10 бананов. Грабить нищего — грех.")
            return

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Напасть!", callback_data=f"rob_{victim_id}")],
            [InlineKeyboardButton("Свалить", callback_data="rob_cancel")]
        ])
        await update.message.reply_text(
            f"🥷 Ты выследил игрока **{victim_data['name']}**!\nУ него в кармане: **{victim_data['bananas']} 🍌**.\nРискнешь напасть и забрать 15%?",
            reply_markup=keyboard
        )

    elif text == "👹 Логово Босса":
        if context.user_data.get("boss_hp", 0) <= 0:
            context.user_data["boss_hp"] = 5000
            await update.message.reply_text(
                "👹 **СТАРЫЙ БОГ ПРОБУДИЛСЯ!**\nУ него **5000 HP**.\n\nЖми кнопку, чтобы атаковать! Каждый удар отнимает бананы и наносит урон.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ Атаковать", callback_data="boss_attack")]])
            )
        else:
            await update.message.reply_text(
                f"👹 Старый Бог уже здесь!\nЕго HP: **{context.user_data['boss_hp']}**.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ Атаковать", callback_data="boss_attack")]])
            )

    elif text == "🌐 Оплатить связь (50 🍌)":
        current_time = time.time()
        last_pay = context.user_data.get("last_internet_pay", 0)
        
        if current_time - last_pay < 86400:
            await update.message.reply_text(f"✅ Связь уже оплачена! Осталось: {int((86400 - (current_time - last_pay)) // 3600)} ч.")
            return
            
        if context.user_data["bananas"] < 50:
            await update.message.reply_text(f"❌ Нет бананов на связь! Надо 50 🍌.")
            return
            
        context.user_data["bananas"] -= 50
        context.user_data["last_internet_pay"] = current_time
        await update.message.reply_text(f"🌐 **ИНТЕРНЕТ ПОДКЛЮЧЕН!**\nОстаток: {context.user_data['bananas']} 🍌", parse_mode="Markdown")

    elif text == "Махаться с чужими":
        STAKE = 5
        if context.user_data["bananas"] < STAKE:
            await update.message.reply_text(f"❌ Для махача надо {STAKE} 🍌!")
            return

        monkeys = context.user_data["monkeys"]
        team = [rarity for rarity, count in monkeys.items() if count > 0]
        team_str = ", ".join(team) if team else "В адиночку 👤"

        enemy_team_list, enemy_total_count, enemy_power = [], 0, 0
        rarities_list = list(RARITIES.keys())
        weights_list = [45, 30, 15, 7, 2.9, 0.1]
        
        for _ in range(random.randint(1, 4)):
            e_rarity = random.choices(rarities_list, weights=weights_list, k=1)[0]
            enemy_team_list.append(e_rarity)
            enemy_total_count += 1
            enemy_power += RARITIES[e_rarity]["income"]
            
        player_power = sum(monkeys.get(rarity, 0) * data["income"] for rarity, data in RARITIES.items())
        final_lose_chance = max(10, min(90, 50 + (enemy_power * 2) - (player_power * 2)))
        attack_type = random.choice(ATTACK_TYPES)

        battle_text = f"⚔️ **{attack_type}!**\n\n👥 **Твоя стая:** {team_str}\n💀 **Вражья стая:** {', '.join(enemy_team_list)}\n\n📉 Шанс атасасать: {final_lose_chance}%"

        try:
            with open(random.choice(WAR_IMAGES), "rb") as photo:
                await update.message.reply_photo(photo=photo, caption=battle_text, parse_mode="Markdown")
        except: await update.message.reply_text(battle_text, parse_mode="Markdown")

        if random.randint(1, 100) > final_lose_chance:
            context.user_data["bananas"] += STAKE
            context.user_data["defeated"] += enemy_total_count
            await update.message.reply_text(f"🎉 **ПАБЕДА!**\nЗагрызено: {enemy_total_count} врагов!\n💰 **+{STAKE} 🍌**\n🍌 Бананов: {context.user_data['bananas']}", parse_mode="Markdown")
        else:
            context.user_data["bananas"] -= STAKE
            loss_msg = f"😢 **АБЛАЖАЛСЯ.**\nТы потерял {STAKE} 🍌.\n"
            if team and random.randint(1, 100) <= 35:
                dead_monkey = random.choice(team)
                context.user_data["monkeys"][dead_monkey] -= 1
                loss_msg += f"\n🥀 В драке пагибла **{dead_monkey}**..."
            loss_msg += f"\n🍌 Бананов: {context.user_data['bananas']}"
            await update.message.reply_text(loss_msg, parse_mode="Markdown")
        await check_achievements(update, context)

    elif text == "🧬 Склещить бибизян":
        monkeys = context.user_data["monkeys"]
        msg = "🧬 **ЛАБАРАТОРИЯ СНОШАНИЯ**\n\n"
        merged = False
        tiers = list(RARITIES.keys())
        for i in range(len(tiers) - 1):
            curr, nxt = tiers[i], tiers[i+1]
            if monkeys[curr] >= 3:
                merge_count = monkeys[curr] // 3
                monkeys[curr] -= merge_count * 3
                monkeys[nxt] += merge_count
                msg += f"✅ {merge_count * 3} шт. {curr} нарожали {merge_count} шт. {nxt}!\n"
                merged = True
        if merged: await update.message.reply_text(msg, parse_mode="Markdown")
        else: await update.message.reply_text("❌ Мало бибизян. Надо по 3 штуки. Иди лутай карыто!", parse_mode="Markdown")

    elif text == "🏆 Вожаки стаи":
        leaderboard = context.bot_data.get("leaderboard", {})
        if not leaderboard: return
        sorted_players = sorted(leaderboard.values(), key=lambda x: x["bananas"], reverse=True)[:5]
        msg = "🏆 **САМЫЕ БОГАТЫЕ ВОЖАКИ:**\n\n"
        for i, p in enumerate(sorted_players, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🔹"
            msg += f"{medal} {p['name']} — {p['bananas']} 🍌 (Загрыз: {p['defeated']} 💀)\n"
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "Вскрыть карыто (5 🍌)":
        if context.user_data["bananas"] < 5:
            await update.message.reply_text(f"❌ Нет бананов! Надо 5 🍌.")
            return

        context.user_data["bananas"] -= 5
        context.user_data["boxes_opened"] += 1
        rarities_list = list(RARITIES.keys())
        weights_list = [data["weight"] for data in RARITIES.values()]
        dropped_rarity = random.choices(rarities_list, weights=weights_list, k=1)[0]
        context.user_data["monkeys"][dropped_rarity] += 1
        
        photo_path = os.path.join(BASE_DIR, random.choice(RARITIES[dropped_rarity]["images"]))
        try:
            with open(photo_path, "rb") as f:
                await update.message.reply_photo(photo=f, caption=f"📦 Из карыта выпрыгнула: **{dropped_rarity}**!\nБананов: {context.user_data['bananas']}", parse_mode="Markdown")
        except FileNotFoundError: await update.message.reply_text(f"📦 Выпала **{dropped_rarity}**! (нет картинки)", parse_mode="Markdown")
        await check_achievements(update, context)

    elif text == "📰 Бибизяни новости":
        news_types = ["weather", "sport", "crime", "science", "ad", "random_event", "meme", "clickbait", "global", "personal"]
        weights = [10, 10, 10, 10, 10, 15, 15, 5, 10, 5] 
        news_type = random.choices(news_types, weights=weights, k=1)[0]
        photo_path = random.choice(MONKEY_NEWS_IMAGES)

        if news_type == "weather": news_text = "🌧 **ПОГОДА:** Завтра ожидается дождь из кокосов."
        elif news_type == "sport": news_text = "🏆 **СПОРТ:** В финале турнира по поеданию бананов победила бибизяна без зубов."
        elif news_type == "crime": news_text = "🚓 **КРИМИНАЛ:** Особо опасная бибизяна ограбила банк на 3 банана."
        elif news_type == "science": news_text = "🔬 **НАУКА:** Ученые доказали, что бибизяны смотрят телевизор."
        elif news_type == "ad": news_text = "📢 **РЕКЛАМА:** Скидки на карыто! 2 по цене 3-х!"
        elif news_type == "random_event": news_text = "🛸 **АНОМАЛИЯ:** НЛО похитило пальму с главной площади."
        elif news_type == "meme": news_text = generate_meme_news()
        elif news_type == "personal": news_text = f"⚡️ **СРОЧНО!** **{context.user_data['name']}** накопил уже **{context.user_data['bananas']} бананов**!"
        elif news_type == "global":
            lb = sorted(context.bot_data.get("leaderboard", {}).values(), key=lambda x: x["bananas"], reverse=True)
            if len(lb) > 1: news_text = f"💰 **БИРЖА:** Сегодня **{lb[0]['name']}** — богатейший вожак с **{lb[0]['bananas']} бананов**! А **{lb[-1]['name']}** — лузер с **{lb[-1]['bananas']}**. Позор!"
            else: news_text = f"📈 **КУРС БАНАНА:** Стабилен! Монополия у **{context.user_data['name']}**."
        elif news_type == "clickbait":
            news_text = "🤯 **ШОК!** Нашли шахту с золотыми бананами!"
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Спуститься (Рискнуть)", callback_data="mine_yes")], [InlineKeyboardButton("Пройти мимо", callback_data="mine_no")]])
            try:
                with open(photo_path, "rb") as photo:
                    await update.message.reply_photo(photo=photo, caption=f"📰 **НОВОСТИ** ⚡️\n\n{news_text}", reply_markup=keyboard, parse_mode="Markdown")
            except: pass
            return 

        try:
            with open(photo_path, "rb") as photo:
                await update.message.reply_photo(photo=photo, caption=f"📰 **НОВОСТИ** ⚡️\n\n{news_text}", parse_mode="Markdown")
        except FileNotFoundError: await update.message.reply_text(f"📰 **НОВОСТИ:** {news_text}", parse_mode="Markdown")

    elif text == "Чо в кармане?":
        monkeys = context.user_data["monkeys"]
        current_speed = sum(monkeys.get(r, 0) * d["income"] for r, d in RARITIES.items())
        is_internet_active = (time.time() - context.user_data.get("last_internet_pay", 0)) < 86400
        
        info_msg = (
            f"💼 **ЧО В КАРМАНЕ:**\n"
            f"🌐 Интернет: {'✅ Вкл' if is_internet_active else '❌ Выкл'}\n"
            f"🍌 Бананы: {context.user_data['bananas']} ( Доход: +{current_speed} 🍌/мин )\n"
            f"💀 Загрызено врагов: {context.user_data['defeated']}\n\n"
            f"🏆 **Твоя стая:**\n"
        )
        for rarity in RARITIES.keys(): info_msg += f"◽ {rarity}: {monkeys.get(rarity, 0)}\n"
        await update.message.reply_text(info_msg, parse_mode="Markdown")

    else:
        await update.message.reply_text("Тыкай кнопки внизу, уа-уа 👇")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    # ШАХТА
    if query.data == "mine_yes":
        if random.choice([True, False]):
            context.user_data["bananas"] += 100
            await query.edit_message_caption(caption=f"💎 **УДАЧА!**\nТы нашел **+100 🍌**!\nБананов: {context.user_data['bananas']}", parse_mode="Markdown")
        else:
            context.user_data["bananas"] = max(0, context.user_data["bananas"] - 20)
            await query.edit_message_caption(caption=f"💀 **ОБВАЛ!**\nТы потерял **20 🍌**.\nБананов: {context.user_data['bananas']}", parse_mode="Markdown")
    elif query.data == "mine_no":
        await query.edit_message_caption(caption=f"🚶‍♂️ Ты прошел мимо. Целее будешь.", parse_mode="Markdown")

    # ОГРАБЛЕНИЕ
    elif query.data.startswith("rob_"):
        if query.data == "rob_cancel":
            await query.edit_message_text("🥷 Ты решил не рисковать и свалил в кусты.")
            return
        
        victim_id = int(query.data.split("_")[1])
        victim_data = context.bot_data["leaderboard"].get(victim_id)
        
        if not victim_data:
            await query.edit_message_text("Игрок куда-то пропал. Ограбление сорвалось.")
            return

        # Шанс успеха 50 на 50
        if random.choice([True, False]):
            # Успех
            stolen = int(victim_data["bananas"] * 0.15)
            context.user_data["bananas"] += stolen
            victim_data["bananas"] -= stolen
            await query.edit_message_text(f"🥷 **УСПЕХ!**\nТы обчистил **{victim_data['name']}** и украл **{stolen} 🍌**!\nТвой баланс: {context.user_data['bananas']}", parse_mode="Markdown")
        else:
            # Провал
            lost = int(context.user_data["bananas"] * 0.10)
            context.user_data["bananas"] = max(0, context.user_data["bananas"] - lost)
            victim_data["bananas"] += lost
            await query.edit_message_text(f"🚨 **ПРОВАЛ!**\n**{victim_data['name']}** поймал тебя за хвост и отобрал **{lost} 🍌** в качестве штрафа!\nТвой баланс: {context.user_data['bananas']}", parse_mode="Markdown")

    # БОСС
    elif query.data == "boss_attack":
        if context.user_data.get("boss_hp", 0) <= 0:
            await query.edit_message_text("👹 Старый Бог уже мертв. Ты его добил.")
            return
            
        if context.user_data["bananas"] < 10:
            await query.answer("❌ У тебя нет 10 бананов, чтобы оплатить удар!", show_alert=True)
            return

        context.user_data["bananas"] -= 10
        
        # Урон зависит от силы стаи
        monkeys = context.user_data["monkeys"]
        player_power = sum(monkeys.get(r, 0) * d["income"] for r, d in RARITIES.items())
        damage = max(10, player_power * random.randint(1, 3))
        
        context.user_data["boss_hp"] -= damage
        
        if context.user_data["boss_hp"] <= 0:
            context.user_data["boss_hp"] = 0
            context.user_data["bananas"] += 500
            if "boss_slayer" not in context.user_data["achievements"]:
                context.user_data["achievements"].append("boss_slayer")
                ach_msg = "\n🎖 **ДОСТИЖЕНИЕ:** Убийца Богов (+500 🍌)!"
            else:
                ach_msg = ""
                
            await query.edit_message_text(
                f"💀 **ПОБЕДА!**\nТы нанес сокрушительный удар на **{damage}** урона и убил Старого Бога!\n\n💰 Награда: **+500 🍌**!{ach_msg}\nТвой баланс: {context.user_data['bananas']}",
                parse_mode="Markdown"
            )
        else:
            # Босс бьет в ответ
            counter_damage = random.randint(5, 20)
            context.user_data["bananas"] = max(0, context.user_data["bananas"] - counter_damage)
            
            hp_bar = "█" * int((context.user_data['boss_hp'] / 5000) * 10) + "░" * (10 - int((context.user_data['boss_hp'] / 5000) * 10))
            
            await query.edit_message_text(
                f"👹 **БИТВА С БОССОМ**\n\n"
                f"❤️ HP Босса: {hp_bar} ({context.user_data['boss_hp']} / 5000)\n\n"
                f"⚔️ Ты нанес **{damage}** урона.\n"
                f"🩸 Босс дал сдачи и отнял у тебя **{counter_damage} 🍌**.\n\n"
                f"Твой баланс: {context.user_data['bananas']} 🍌",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ Атаковать", callback_data="boss_attack")]]),
                parse_mode="Markdown"
            )

if __name__ == "__main__":
    print("Запускаю банановую бибизяну...")
    req = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0, write_timeout=30.0, pool_timeout=30.0)
    app = ApplicationBuilder().token(TOKEN).request(req).get_updates_request(req).build()
    job_queue = app.job_queue
    job_queue.run_repeating(passive_income_callback, interval=60, first=10)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler_text))
    app.add_handler(CallbackQueryHandler(callback_handler)) 
    print("✅ Бибизяна успешно вырвалась на волю!")
    app.run_polling()