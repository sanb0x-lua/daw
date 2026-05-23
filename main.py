import discord
from discord.ext import commands
from discord.ui import View, Button
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont
import io
import os
import sys
import json
import aiohttp
import asyncio
from aiohttp import web

PID_FILE = "bot.pid"

try:
    with open(PID_FILE, 'x') as f:
        f.write(str(os.getpid()))
except FileExistsError:
    try:
        with open(PID_FILE, 'r') as f:
            old_pid = int(f.read().strip())
            os.kill(old_pid, 0)
            print(f"Бот уже запущен (PID: {old_pid})")
            sys.exit(0)
    except:
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    TOKEN = "ой бляяя"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
intents.guilds = True
intents.moderation = True
intents.bans = True
intents.reactions = True

bot = commands.Bot(command_prefix="S!", intents=intents)

messages_log = defaultdict(list)
logs_list = defaultdict(list)
log_channels = {}
LOGS_FILE = "logs_cache.json"

def save_logs_to_file():
    data = {}
    for guild_id, logs in logs_list.items():
        data[str(guild_id)] = logs
    with open(LOGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_logs_from_file():
    global logs_list
    if os.path.exists(LOGS_FILE):
        try:
            with open(LOGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for guild_id, logs in data.items():
                    logs_list[int(guild_id)] = logs
        except:
            pass

def get_font(size):
    try:
        return ImageFont.truetype("assets/arial.ttf", size)
    except:
        try:
            return ImageFont.truetype("arial.ttf", size)
        except:
            return ImageFont.load_default()

def draw_rounded_rect(draw, xy, radius, fill=None):
    x1, y1, x2, y2 = xy
    draw.rectangle([x1+radius, y1, x2-radius, y2], fill=fill)
    draw.rectangle([x1, y1+radius, x2, y2-radius], fill=fill)
    draw.pieslice([x1, y1, x1+radius*2, y1+radius*2], 180, 270, fill=fill)
    draw.pieslice([x2-radius*2, y1, x2, y1+radius*2], 270, 360, fill=fill)
    draw.pieslice([x1, y2-radius*2, x1+radius*2, y2], 90, 180, fill=fill)
    draw.pieslice([x2-radius*2, y2-radius*2, x2, y2], 0, 90, fill=fill)

def load_background():
    bg_path = "assets/bg.png"
    if os.path.exists(bg_path):
        bg = Image.open(bg_path)
        bg = bg.resize((1000, 700))
        return bg.convert('RGB')
    else:
        return Image.new('RGB', (1000, 700), (30, 35, 60))

def format_date(dt):
    if dt:
        return dt.strftime("%d.%m.%Y %H:%M")
    return "Неизвестно"

def get_msk_time():
    return datetime.now(timezone.utc + timedelta(hours=3)).strftime("%d.%m %H:%M:%S")

def add_log(guild_id, log_type, user, channel, content):
    log_entry = {
        "type": log_type[:25],
        "user": user[:25],
        "channel": channel[:20] if channel else "-",
        "content": content[:55],
        "time": get_msk_time()
    }
    logs_list[guild_id].append(log_entry)
    if len(logs_list[guild_id]) > 1000:
        logs_list[guild_id] = logs_list[guild_id][-800:]
    save_logs_to_file()

@bot.event
async def on_guild_channel_create(channel):
    if channel.guild:
        add_log(channel.guild.id, "Создан канал", "Система", channel.name, f"#{channel.name}")

@bot.event
async def on_guild_channel_delete(channel):
    if channel.guild:
        add_log(channel.guild.id, "Удалён канал", "Система", channel.name, f"#{channel.name} удалён")

@bot.event
async def on_guild_channel_update(before, after):
    if before.guild and before.name != after.name:
        add_log(before.guild.id, "Переимен канал", "Система", after.name, f"{before.name} -> {after.name}")

@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel != after.channel:
        if after.channel:
            add_log(member.guild.id, "Зашёл в войс", member.name, after.channel.name, f"Вошёл в {after.channel.name}")
        elif before.channel:
            add_log(member.guild.id, "Вышел из войса", member.name, before.channel.name, f"Вышел из {before.channel.name}")

@bot.event
async def on_member_join(member):
    add_log(member.guild.id, "Присоединился", member.name, "-", "Новый участник")

@bot.event
async def on_member_remove(member):
    add_log(member.guild.id, "Покинул/Кик", member.name, "-", "Участник покинул")

@bot.event
async def on_member_ban(guild, user):
    add_log(guild.id, "Бан", user.name, "-", "Забанен")

@bot.event
async def on_member_unban(guild, user):
    add_log(guild.id, "Разбан", user.name, "-", "Разбанен")

@bot.event
async def on_guild_role_create(role):
    add_log(role.guild.id, "Создана роль", "Система", role.name, "Новая роль")

@bot.event
async def on_guild_role_delete(role):
    add_log(role.guild.id, "Удалена роль", "Система", role.name, "Роль удалена")

@bot.event
async def on_guild_role_update(before, after):
    if before.name != after.name:
        add_log(before.guild.id, "Переимен роль", "Система", after.name, f"{before.name} -> {after.name}")

@bot.event
async def on_message_delete(message):
    if message.guild and message.author and not message.author.bot:
        add_log(message.guild.id, "Удаление сообщ", message.author.name, message.channel.name, message.content[:55] if message.content else "(нет текста)")

@bot.event
async def on_message_edit(before, after):
    if before.guild and before.author and not before.author.bot:
        if before.content != after.content:
            add_log(before.guild.id, "Редакт сообщ", before.author.name, before.channel.name, f"{before.content[:30]} -> {after.content[:30]}")

@bot.event
async def on_ready():
    load_logs_from_file()
    print(f'Bot ready: {bot.user}')
    if not os.path.exists("assets"):
        os.makedirs("assets")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.guild:
        messages_log[message.guild.id].append({
            "user": message.author.name,
            "channel": message.channel.name,
            "time": datetime.now(timezone.utc)
        })
        if len(messages_log[message.guild.id]) > 5000:
            messages_log[message.guild.id] = messages_log[message.guild.id][-4000:]
    await bot.process_commands(message)


class StatsView(View):
    def __init__(self, ctx, guild_id, messages_log):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.guild_id = guild_id
        self.messages_log = messages_log
        self.current_days = 1
    
    async def send(self):
        await self.update_display()
    
    async def update_display(self, interaction=None):
        CARD_WIDTH, CARD_HEIGHT = 1000, 700
        bg = load_background()
        img = bg.copy()
        draw = ImageDraw.Draw(img)
        
        font_title = get_font(30)
        font_large = get_font(52)
        font_normal = get_font(22)
        font_small = get_font(18)
        font_bold = get_font(22)
        
        margin, radius = 25, 25
        now = datetime.now(timezone.utc)
        guild_msgs = self.messages_log[self.guild_id]
        
        def msg_count(d):
            cutoff = now - timedelta(days=d)
            return len([m for m in guild_msgs if m["time"] > cutoff])
        
        dark_color = (40, 44, 52, 180)
        card_layer = Image.new('RGBA', (CARD_WIDTH, CARD_HEIGHT), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card_layer)
        draw_rounded_rect(card_draw, [margin, margin, CARD_WIDTH-margin, CARD_HEIGHT-margin], radius, fill=dark_color)
        img = Image.alpha_composite(img.convert('RGBA'), card_layer)
        draw = ImageDraw.Draw(img)
        
        x, y, padding = margin, margin, 30
        draw.text((x+padding, y+20), "Статистика сервера", fill=(255,255,255), font=font_title)
        draw.text((x+padding, y+60), self.ctx.guild.name, fill=(200,200,200), font=font_small)
        draw.text((x+padding, y+110), str(len(guild_msgs)), fill=(255,255,255), font=font_large)
        draw.text((x+padding, y+165), "всего сообщений", fill=(180,180,180), font=font_small)
        
        period_y = y + 220
        periods = [(1, "1 день"), (7, "7 дней"), (30, "30 дней")]
        for i, (d, name) in enumerate(periods):
            x_pos = x+padding + i*150
            draw.text((x_pos, period_y), name, fill=(180,180,180), font=font_small)
            draw.text((x_pos, period_y+32), str(msg_count(d)), fill=(255,255,255), font=font_bold)
        
        cutoff = now - timedelta(days=self.current_days)
        filtered = [m for m in guild_msgs if m["time"] > cutoff]
        user_counts = defaultdict(int)
        for m in filtered:
            user_counts[m["user"]] += 1
        top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        draw.text((x+padding, y+310), "Топ пользователи", fill=(255,255,255), font=font_normal)
        y_user = y + 355
        for i, (user, count) in enumerate(top_users):
            color = (255,255,255) if i == 0 else (220,220,220) if i == 1 else (200,200,200) if i == 2 else (180,180,180)
            draw.text((x+padding+5, y_user + i*40), f"{i+1}. {user}", fill=color, font=font_small)
            draw.text((x+CARD_WIDTH-padding-70, y_user + i*40), str(count), fill=color, font=font_small)
        
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        file = discord.File(buf, filename="stats.png")
        embed = discord.Embed(color=0xFFFFFF)
        embed.set_image(url="attachment://stats.png")
        
        self.clear_items()
        btn1 = Button(label="1 день", style=discord.ButtonStyle.secondary)
        btn7 = Button(label="7 дней", style=discord.ButtonStyle.secondary)
        btn30 = Button(label="30 дней", style=discord.ButtonStyle.secondary)
        
        async def day_callback(d):
            async def callback(i):
                self.current_days = d
                await self.update_display(i)
            return callback
        
        btn1.callback = await day_callback(1)
        btn7.callback = await day_callback(7)
        btn30.callback = await day_callback(30)
        
        self.add_item(btn1)
        self.add_item(btn7)
        self.add_item(btn30)
        
        if interaction:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await self.ctx.send(embed=embed, file=file, view=self)

async def get_avatar_image(user):
    async with aiohttp.ClientSession() as session:
        async with session.get(user.display_avatar.url) as resp:
            if resp.status == 200:
                img_data = await resp.read()
                avatar = Image.open(io.BytesIO(img_data))
                return avatar.convert('RGBA')
    return None

def create_circle_avatar(avatar_img, size=35):
    avatar = avatar_img.resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new('L', (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse([(0, 0), (size, size)], fill=255)
    result = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    result.paste(avatar, (0, 0), mask)
    return result

class LeaderBoardView(View):
    def __init__(self, ctx, guild_id, messages_log):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.guild_id = guild_id
        self.messages_log = messages_log
        self.current_days = 1
        self.current_page = 0
        self.avatar_cache = {}
    
    async def send(self):
        await self.update_display()
    
    async def update_display(self, interaction=None):
        CARD_WIDTH, CARD_HEIGHT = 1000, 700
        bg = load_background()
        img = bg.copy()
        draw = ImageDraw.Draw(img)
        
        font_title = get_font(30)
        font_normal = get_font(20)
        font_small = get_font(17)
        font_bold = get_font(20)
        
        margin, radius = 25, 25
        now = datetime.now(timezone.utc)
        guild_msgs = self.messages_log[self.guild_id]
        
        cutoff = now - timedelta(days=self.current_days)
        filtered = [m for m in guild_msgs if m["time"] > cutoff]
        user_counts = defaultdict(int)
        for m in filtered:
            user_counts[m["user"]] += 1
        top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
        
        items_per_page = 14
        total_pages = max(1, (len(top_users) + items_per_page - 1) // items_per_page)
        self.current_page = max(0, min(self.current_page, total_pages - 1))
        start = self.current_page * items_per_page
        current_users = top_users[start:start+items_per_page]
        
        dark_color = (40, 44, 52, 180)
        card_layer = Image.new('RGBA', (CARD_WIDTH, CARD_HEIGHT), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card_layer)
        draw_rounded_rect(card_draw, [margin, margin, CARD_WIDTH-margin, CARD_HEIGHT-margin], radius, fill=dark_color)
        img = Image.alpha_composite(img.convert('RGBA'), card_layer)
        draw = ImageDraw.Draw(img)
        
        x, y, padding = margin, margin, 30
        period_name = {1: "1 день", 7: "7 дней", 30: "30 дней"}
        draw.text((x+padding, y+20), f"Лидербоард - {period_name.get(self.current_days, 'все время')}", fill=(255,255,255), font=font_title)
        draw.text((x+padding, y+60), f"Всего участников: {len(user_counts)}", fill=(200,200,200), font=font_small)
        draw.text((x+padding, y+90), f"Страница {self.current_page+1} из {total_pages}", fill=(200,200,200), font=font_small)
        
        y_header = y + 135
        draw.text((x+padding+45, y_header), "Пользователь", fill=(200,200,200), font=font_normal)
        draw.text((x+padding+320, y_header), "Сообщений", fill=(200,200,200), font=font_normal)
        
        y_user = y + 175
        row_height = 38
        for i, (user, count) in enumerate(current_users):
            rank = start + i + 1
            color = (255,255,255) if rank == 1 else (220,220,220) if rank == 2 else (200,200,200) if rank == 3 else (180,180,180)
            draw.text((x+padding+10, y_user + i*row_height), str(rank), fill=color, font=font_bold)
            
            member = discord.utils.get(self.ctx.guild.members, name=user)
            if member and member.id not in self.avatar_cache:
                avatar_img = await get_avatar_image(member)
                if avatar_img:
                    self.avatar_cache[member.id] = avatar_img
            if member and member.id in self.avatar_cache:
                avatar = create_circle_avatar(self.avatar_cache[member.id], 32)
                img.paste(avatar, (x+padding+38, y_user + i*row_height + 2), avatar)
            
            draw.text((x+padding+80, y_user + i*row_height + 5), user[:25], fill=(255,255,255), font=font_small)
            draw.text((x+padding+320, y_user + i*row_height + 5), str(count), fill=color, font=font_bold)
        
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        file = discord.File(buf, filename="leaderboard.png")
        embed = discord.Embed(color=0xFFFFFF)
        embed.set_image(url="attachment://leaderboard.png")
        
        self.clear_items()
        btn1 = Button(label="1 день", style=discord.ButtonStyle.secondary)
        btn7 = Button(label="7 дней", style=discord.ButtonStyle.secondary)
        btn30 = Button(label="30 дней", style=discord.ButtonStyle.secondary)
        btn_prev = Button(label="Назад", style=discord.ButtonStyle.secondary)
        btn_next = Button(label="Вперёд", style=discord.ButtonStyle.secondary)
        
        async def day_callback(d):
            async def callback(i):
                self.current_days = d
                self.current_page = 0
                await self.update_display(i)
            return callback
        
        async def prev_callback(i):
            if self.current_page > 0:
                self.current_page -= 1
                await self.update_display(i)
        
        async def next_callback(i):
            if self.current_page < total_pages - 1:
                self.current_page += 1
                await self.update_display(i)
        
        btn1.callback = await day_callback(1)
        btn7.callback = await day_callback(7)
        btn30.callback = await day_callback(30)
        btn_prev.callback = prev_callback
        btn_next.callback = next_callback
        
        self.add_item(btn1)
        self.add_item(btn7)
        self.add_item(btn30)
        self.add_item(btn_prev)
        self.add_item(btn_next)
        
        if interaction:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await self.ctx.send(embed=embed, file=file, view=self)

class ProfileView(View):
    def __init__(self, ctx, guild_id, messages_log, target_user):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.guild_id = guild_id
        self.messages_log = messages_log
        self.target_user = target_user
        self.avatar_img = None
    
    async def send(self):
        await self.update_display()
    
    async def get_avatar(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(self.target_user.display_avatar.url) as resp:
                if resp.status == 200:
                    img_data = await resp.read()
                    avatar = Image.open(io.BytesIO(img_data))
                    return avatar.convert('RGBA')
        return None
    
    def create_circle_avatar(self, avatar_img, size=90):
        avatar = avatar_img.resize((size, size), Image.Resampling.LANCZOS)
        mask = Image.new('L', (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse([(0, 0), (size, size)], fill=255)
        result = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        result.paste(avatar, (0, 0), mask)
        border = Image.new('RGBA', (size+8, size+8), (0, 0, 0, 0))
        border_draw = ImageDraw.Draw(border)
        border_draw.ellipse([(4, 4), (size+4, size+4)], outline=(200,200,200), width=3)
        border.paste(result, (4, 4), result)
        return border
    
    async def update_display(self, interaction=None):
        CARD_WIDTH, CARD_HEIGHT = 1000, 700
        bg = load_background()
        img = bg.copy()
        draw = ImageDraw.Draw(img)
        
        font_title = get_font(26)
        font_large = get_font(34)
        font_normal = get_font(18)
        font_small = get_font(14)
        font_bold = get_font(19)
        
        margin, radius = 20, 25
        now = datetime.now(timezone.utc)
        guild_msgs = self.messages_log[self.guild_id]
        user = self.target_user
        member = self.ctx.guild.get_member(user.id)
        
        user_msgs = [m for m in guild_msgs if m["user"] == user.name]
        total_msgs = len(user_msgs)
        msgs_1d = len([m for m in user_msgs if m["time"] > now - timedelta(days=1)])
        msgs_7d = len([m for m in user_msgs if m["time"] > now - timedelta(days=7)])
        msgs_30d = len([m for m in user_msgs if m["time"] > now - timedelta(days=30)])
        
        channel_counts = defaultdict(int)
        for m in user_msgs:
            channel_counts[m["channel"]] += 1
        favorite_channel = max(channel_counts.items(), key=lambda x: x[1])[0] if channel_counts else "Нет"
        favorite_channel_count = channel_counts.get(favorite_channel, 0)
        
        total_guild_msgs = len(guild_msgs)
        activity_percent = (total_msgs / total_guild_msgs * 100) if total_guild_msgs > 0 else 0
        
        all_users = defaultdict(int)
        for m in guild_msgs:
            all_users[m["user"]] += 1
        sorted_users = sorted(all_users.items(), key=lambda x: x[1], reverse=True)
        rank = 1
        for i, (u, _) in enumerate(sorted_users):
            if u == user.name:
                rank = i + 1
                break
        
        achievements = []
        if total_msgs >= 100:
            achievements.append("100 сообщений")
        if total_msgs >= 1000:
            achievements.append("1000 сообщений")
        if total_msgs >= 5000:
            achievements.append("5000 сообщений")
        if total_msgs >= 10000:
            achievements.append("10000 сообщений")
        if msgs_30d >= 300:
            achievements.append("300 за месяц")
        if rank == 1:
            achievements.append("Лидер сервера")
        
        if member:
            status = member.status
            if status == discord.Status.online:
                status_text, status_color = "В сети", (87,242,135)
            elif status == discord.Status.idle:
                status_text, status_color = "Не активен", (251,211,141)
            elif status == discord.Status.dnd:
                status_text, status_color = "Не беспокоить", (237,66,69)
            else:
                status_text, status_color = "Не в сети", (116,127,141)
        else:
            status_text, status_color = "Не в сети", (116,127,141)
        
        roles_text = ""
        if member and len(member.roles) > 1:
            roles_list = [role.name for role in member.roles if role.name != "@everyone"][:4]
            roles_text = ", ".join(roles_list)
            if len(member.roles) > 5:
                roles_text += f" +{len(member.roles)-5}"
        else:
            roles_text = "Нет ролей"
        
        dark_color = (40, 44, 52, 180)
        card_layer = Image.new('RGBA', (CARD_WIDTH, CARD_HEIGHT), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card_layer)
        draw_rounded_rect(card_draw, [margin, margin, CARD_WIDTH-margin, CARD_HEIGHT-margin], radius, fill=dark_color)
        img = Image.alpha_composite(img.convert('RGBA'), card_layer)
        draw = ImageDraw.Draw(img)
        
        x, y, padding = margin, margin, 22
        
        draw.text((x+padding, y+12), "Профиль пользователя", fill=(255,255,255), font=font_title)
        
        if self.avatar_img is None:
            self.avatar_img = await self.get_avatar()
        if self.avatar_img:
            avatar = self.create_circle_avatar(self.avatar_img, 85)
            img.paste(avatar, (x+padding, y+50), avatar)
        else:
            draw.ellipse([x+padding, y+50, x+padding+85, y+135], fill=(80,80,80), outline=(200,200,200), width=3)
        
        draw.text((x+padding+105, y+55), user.display_name, fill=(255,255,255), font=font_bold)
        draw.text((x+padding+105, y+80), f"@{user.name}", fill=(200,200,200), font=font_small)
        draw.text((x+padding+105, y+100), f"Глобальное имя: {user.global_name or 'Нет'}", fill=(180,180,180), font=font_small)
        draw.ellipse([x+padding+105, y+123, x+padding+118, y+136], fill=status_color)
        draw.text((x+padding+128, y+123), status_text, fill=(200,200,200), font=font_small)
        draw.text((x+padding+105, y+148), f"ID: {user.id}", fill=(150,150,150), font=font_small)
        
        stats_y = y + 185
        draw.text((x+padding, stats_y), "Статистика сообщений", fill=(255,255,255), font=font_normal)
        draw.text((x+padding, stats_y+25), "Всего", fill=(180,180,180), font=font_small)
        draw.text((x+padding, stats_y+45), str(total_msgs), fill=(255,255,255), font=font_bold)
        draw.text((x+padding+95, stats_y+25), "1 день", fill=(180,180,180), font=font_small)
        draw.text((x+padding+95, stats_y+45), str(msgs_1d), fill=(255,255,255), font=font_small)
        draw.text((x+padding+175, stats_y+25), "7 дней", fill=(180,180,180), font=font_small)
        draw.text((x+padding+175, stats_y+45), str(msgs_7d), fill=(255,255,255), font=font_small)
        draw.text((x+padding+255, stats_y+25), "30 дней", fill=(180,180,180), font=font_small)
        draw.text((x+padding+255, stats_y+45), str(msgs_30d), fill=(255,255,255), font=font_small)
        draw.text((x+padding+350, stats_y+25), "Ранг", fill=(180,180,180), font=font_small)
        draw.text((x+padding+350, stats_y+45), f"#{rank}", fill=(255,255,255), font=font_small)
        
        draw.text((x+padding, stats_y+80), f"Любимый канал: #{favorite_channel} ({favorite_channel_count} сообщ.)", fill=(200,200,200), font=font_small)
        draw.text((x+padding, stats_y+103), f"Процент активности: {activity_percent:.2f}%", fill=(200,200,200), font=font_small)
        
        acc_y = stats_y + 145
        draw.text((x+padding, acc_y), "Информация об аккаунте", fill=(255,255,255), font=font_normal)
        draw.text((x+padding, acc_y+28), "Аккаунт создан", fill=(180,180,180), font=font_small)
        draw.text((x+padding, acc_y+50), format_date(user.created_at), fill=(220,220,220), font=font_small)
        draw.text((x+padding, acc_y+75), "Присоединился", fill=(180,180,180), font=font_small)
        draw.text((x+padding, acc_y+97), format_date(member.joined_at) if member else "Неизвестно", fill=(220,220,220), font=font_small)
        draw.text((x+padding+280, acc_y+28), "Буст сервера", fill=(180,180,180), font=font_small)
        boost_text = f"С {format_date(member.premium_since)}" if (member and member.premium_since) else "Нет"
        draw.text((x+padding+280, acc_y+50), boost_text, fill=(220,220,220), font=font_small)
        draw.text((x+padding+280, acc_y+75), "Роли", fill=(180,180,180), font=font_small)
        draw.text((x+padding+280, acc_y+97), roles_text[:35], fill=(220,220,220), font=font_small)
        
        ach_y = acc_y + 135
        draw.text((x+padding, ach_y), "Достижения", fill=(255,255,255), font=font_normal)
        ach_text = "  ".join(achievements[:5]) if achievements else "Пока нет достижений"
        draw.text((x+padding, ach_y+28), ach_text[:80], fill=(255,215,0) if achievements else (180,180,180), font=font_small)
        
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        file = discord.File(buf, filename="profile.png")
        embed = discord.Embed(color=0xFFFFFF)
        embed.set_image(url="attachment://profile.png")
        
        if interaction:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await self.ctx.send(embed=embed, file=file, view=self)

@bot.command()
async def setL(ctx, channel: discord.TextChannel = None):
    if channel is None:
        channel = ctx.channel
    log_channels[ctx.guild.id] = channel.id
    await ctx.send(f"Установлено: {channel.mention}")

@bot.command()
async def delL(ctx):
    if ctx.guild.id in log_channels:
        del log_channels[ctx.guild.id]
        await ctx.send("Удалено!")
    else:
        await ctx.send("Иди нахуй.")

class LogsView(View):
    def __init__(self, ctx, guild_id, logs_list):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.guild_id = guild_id
        self.logs_list = logs_list
        self.current_page = 0
        self.items_per_page = 10
    
    async def send(self):
        await self.update_display()
    
    async def update_display(self, interaction=None):
        CARD_WIDTH, CARD_HEIGHT = 1000, 700
        bg = load_background()
        img = bg.copy()
        draw = ImageDraw.Draw(img)
        
        font_title = get_font(30)
        font_normal = get_font(18)
        font_small = get_font(14)
        
        margin, radius = 25, 25
        logs = self.logs_list[self.guild_id].copy()
        logs.reverse()
        total_pages = max(1, (len(logs) + self.items_per_page - 1) // self.items_per_page)
        self.current_page = max(0, min(self.current_page, total_pages - 1))
        start = self.current_page * self.items_per_page
        current_logs = logs[start:start+self.items_per_page]
        
        dark_color = (40, 44, 52, 180)
        card_layer = Image.new('RGBA', (CARD_WIDTH, CARD_HEIGHT), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card_layer)
        draw_rounded_rect(card_draw, [margin, margin, CARD_WIDTH-margin, CARD_HEIGHT-margin], radius, fill=dark_color)
        img = Image.alpha_composite(img.convert('RGBA'), card_layer)
        draw = ImageDraw.Draw(img)
        
        x, y, padding = margin, margin, 25
        draw.text((x+padding, y+20), "Логи сервера", fill=(255,255,255), font=font_title)
        draw.text((x+padding, y+55), f"Страница {self.current_page+1} из {total_pages}", fill=(200,200,200), font=font_small)
        
        if not logs:
            draw.text((x+padding, y+100), "Логов пока нет", fill=(150,150,150), font=font_normal)
        else:
            y_header = y + 95
            draw.text((x+padding+5, y_header), "Тип", fill=(200,200,200), font=font_small)
            draw.text((x+padding+140, y_header), "Пользователь", fill=(200,200,200), font=font_small)
            draw.text((x+padding+280, y_header), "Канал", fill=(200,200,200), font=font_small)
            draw.text((x+padding+400, y_header), "Действие", fill=(200,200,200), font=font_small)
            draw.text((x+padding+680, y_header), "Время", fill=(200,200,200), font=font_small)
            
            y_log = y_header + 25
            row_height = 52
            for i, log in enumerate(current_logs):
                y_pos = y_log + i * row_height
                draw.text((x+padding+5, y_pos), log["type"][:18], fill=(220,220,220), font=font_small)
                draw.text((x+padding+140, y_pos), log["user"][:20], fill=(255,255,255), font=font_small)
                draw.text((x+padding+280, y_pos), log["channel"][:15], fill=(220,220,220), font=font_small)
                draw.text((x+padding+400, y_pos), log["content"][:35], fill=(200,200,200), font=font_small)
                draw.text((x+padding+680, y_pos), log["time"], fill=(180,180,180), font=font_small)
        
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        file = discord.File(buf, filename="logs.png")
        embed = discord.Embed(color=0xFFFFFF)
        embed.set_image(url="attachment://logs.png")
        
        self.clear_items()
        btn_prev = Button(label="Назад", style=discord.ButtonStyle.secondary)
        btn_next = Button(label="Вперёд", style=discord.ButtonStyle.secondary)
        btn_refresh = Button(label="Обновить", style=discord.ButtonStyle.primary)
        
        async def prev_callback(i):
            if self.current_page > 0:
                self.current_page -= 1
                await self.update_display(i)
        
        async def next_callback(i):
            if self.current_page < total_pages - 1:
                self.current_page += 1
                await self.update_display(i)
        
        async def refresh_callback(i):
            await self.update_display(i)
        
        btn_prev.callback = prev_callback
        btn_next.callback = next_callback
        btn_refresh.callback = refresh_callback
        
        self.add_item(btn_prev)
        self.add_item(btn_next)
        self.add_item(btn_refresh)
        
        if interaction:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await self.ctx.send(embed=embed, file=file, view=self)

@bot.command()
async def L(ctx):
    if ctx.guild.id not in log_channels:
        await ctx.send("Иди нахуй")
        return
    if ctx.channel.id != log_channels[ctx.guild.id]:
        await ctx.send(f"Тебе туда: <#{log_channels[ctx.guild.id]}>")
        return
    view = LogsView(ctx, ctx.guild.id, logs_list)
    await view.send()

class HelpView(View):
    def __init__(self):
        super().__init__(timeout=120)
    
    async def send(self, ctx):
        await self.update_display(ctx)
    
    async def update_display(self, ctx, interaction=None):
        CARD_WIDTH, CARD_HEIGHT = 1000, 700
        bg = load_background()
        img = bg.copy()
        draw = ImageDraw.Draw(img)
        
        font_title = get_font(36)
        font_normal = get_font(24)
        font_small = get_font(20)
        font_bold = get_font(26)
        
        margin, radius = 25, 25
        dark_color = (40, 44, 52, 180)
        card_layer = Image.new('RGBA', (CARD_WIDTH, CARD_HEIGHT), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card_layer)
        draw_rounded_rect(card_draw, [margin, margin, CARD_WIDTH-margin, CARD_HEIGHT-margin], radius, fill=dark_color)
        img = Image.alpha_composite(img.convert('RGBA'), card_layer)
        draw = ImageDraw.Draw(img)
        
        x, y, padding = margin, margin, 30
        draw.text((x+padding, y+30), "Помощь", fill=(255,255,255), font=font_title)
        draw.text((x+padding, y+80), "Список доступных команд", fill=(200,200,200), font=font_small)
        
        commands_y = y + 150
        commands = [
            ("S!S", "Статистика сервера"),
            ("S!LB", "Лидербоард"),
            ("S!P", "Профиль (S!P @user)"),
            ("S!L", "Логи сервера"),
            ("S!setL", "Установить канал для логов"),
            ("S!delL", "Удалить канал для логов"),
            ("S!H", "Помощь")
        ]
        
        for i, (cmd, desc) in enumerate(commands):
            draw.text((x+padding, commands_y + i*55), cmd, fill=(255,255,255), font=font_bold)
            draw.text((x+padding+200, commands_y + i*55 + 5), desc, fill=(200,200,200), font=font_normal)
        
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        file = discord.File(buf, filename="help.png")
        embed = discord.Embed(color=0xFFFFFF)
        embed.set_image(url="attachment://help.png")
        
        self.clear_items()
        btn_stats = Button(label="S!S", style=discord.ButtonStyle.primary)
        btn_lb = Button(label="S!LB", style=discord.ButtonStyle.primary)
        btn_profile = Button(label="S!P", style=discord.ButtonStyle.primary)
        btn_logs = Button(label="S!L", style=discord.ButtonStyle.primary)
        
        async def stats_callback(i):
            await ctx.invoke(ctx.bot.get_command('S'))
        async def lb_callback(i):
            await ctx.invoke(ctx.bot.get_command('LB'))
        async def profile_callback(i):
            await ctx.invoke(ctx.bot.get_command('P'))
        async def logs_callback(i):
            await ctx.invoke(ctx.bot.get_command('L'))
        
        btn_stats.callback = stats_callback
        btn_lb.callback = lb_callback
        btn_profile.callback = profile_callback
        btn_logs.callback = logs_callback
        
        self.add_item(btn_stats)
        self.add_item(btn_lb)
        self.add_item(btn_profile)
        self.add_item(btn_logs)
        
        if interaction:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await ctx.send(embed=embed, file=file, view=self)

@bot.command()
async def S(ctx):
    if not ctx.guild:
        return
    view = StatsView(ctx, ctx.guild.id, messages_log)
    await view.send()

@bot.command()
async def LB(ctx):
    if not ctx.guild:
        return
    view = LeaderBoardView(ctx, ctx.guild.id, messages_log)
    await view.send()

@bot.command()
async def P(ctx, member: discord.Member = None):
    if not ctx.guild:
        return
    target = member or ctx.author
    view = ProfileView(ctx, ctx.guild.id, messages_log, target)
    await view.send()

@bot.command()
async def H(ctx):
    view = HelpView()
    await view.send(ctx)

async def health_check(request):
    return web.Response(text="Bot is alive!")

app = web.Application()
app.router.add_get('/', health_check)

async def run_web():
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server on port {port}")

async def main():
    await asyncio.gather(run_web(), bot.start(TOKEN))

if __name__ == "__main__":
    asyncio.run(main())
