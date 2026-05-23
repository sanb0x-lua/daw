import discord
from discord.ext import commands
from aiohttp import web
import asyncio
import os

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="S!", intents=intents)

@bot.event
async def on_ready():
    print(f'Bot ready: {bot.user}')

@bot.command()
async def test(ctx):
    await ctx.send("ТЫ ДОЛБОЕБ ОШИБКА В КОДЕ БЫЛА")

@bot.command()
async def S(ctx):
    await ctx.send("Статистика сервера (тест)")

@bot.command()
async def H(ctx):
    await ctx.send("Команды: S!test, S!S, S!H")

async def health_check(request):
    return web.Response(text="Bot is alive!")

app = web.Application()
app.router.add_get('/', health_check)

async def run_web():
    port = 10000
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server on port {port}")

async def main():
    await asyncio.gather(run_web(), bot.start(TOKEN))

if __name__ == "__main__":
    asyncio.run(main())