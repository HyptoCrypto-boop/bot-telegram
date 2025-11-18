import os
import json
import gspread
from gspread_formatting import *
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)
import asyncio

# ============================
# CONFIG GOOGLE SHEETS
# ============================

# Coger el JSON de credenciales desde variable de entorno
CREDS_JSON = os.environ.get("GOOGLE_CREDS")
if not CREDS_JSON:
    raise ValueError("No se ha definido la variable de entorno GOOGLE_CREDS")

creds_dict = json.loads(CREDS_JSON)
CLIENT = gspread.service_account_from_dict(creds_dict)

SPREADSHEET_NAME = "Cuentas telegram"
SHEET_NAME = "Hoja 1"
sheet = CLIENT.open(SPREADSHEET_NAME).worksheet(SHEET_NAME)

# Columnas (1–7)
COL_USER = 1
COL_PASS = 2
COL_MAIL = 3
COL_MAILPASS = 4
COL_ESTADO = 5
COL_STREAMER = 6
COL_PAIS = 7

# ============================
# FORMATOS DE COLOR
# ============================

GREEN = Color(0.80, 0.94, 0.80)   # FUNCIONA
RED = Color(0.96, 0.80, 0.80)     # NO_FUNCIONA
YELLOW = Color(0.98, 0.93, 0.76)  # LATAM

def color_fila(fila, color):
    fmt = CellFormat(backgroundColor=color)
    format_cell_range(sheet, f"A{fila}:G{fila}", fmt)

# ============================
# TRACKING DE CUENTAS POR USUARIO
# ============================

filas_usuario = {}

# ============================
# HANDLERS TELEGRAM
# ============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hola! 👋\nUsa /pedir_cuenta para obtener una cuenta disponible."
    )

async def pedir_cuenta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.from_user.username
    if not user_name:
        user_name = update.message.from_user.first_name

    num_rows = len(sheet.get_all_values())
    for row_number in range(2, num_rows + 1):
        values = sheet.row_values(row_number)
        while len(values) < 7:
            values.append("")

        estado = values[COL_ESTADO - 1].strip().lower()
        pais = values[COL_PAIS - 1].strip()

        if estado == "libre" and pais.upper() != "LATAM":
            cuenta = values[COL_USER - 1]
            password = values[COL_PASS - 1]
            correo = values[COL_MAIL - 1]
            pass_correo = values[COL_MAILPASS - 1]
            pais_text = pais if pais else "Desconocido"

            filas_usuario.setdefault(user_name, []).append({"fila": row_number, "cuenta": cuenta})

            await asyncio.to_thread(sheet.update_cell, row_number, COL_ESTADO, "FUNCIONA")
            await asyncio.to_thread(sheet.update_cell, row_number, COL_STREAMER, f"@{user_name}")
            await asyncio.to_thread(color_fila, row_number, GREEN)

            keyboard = [
                [
                    InlineKeyboardButton("❌ No Funciona", callback_data=f"NO_FUNCIONA|{cuenta}"),
                    InlineKeyboardButton("🟨 LATAM", callback_data=f"LATAM|{cuenta}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"Tu cuenta asignada es:\n\n"
                f"🎮 *Cuenta*: `{cuenta}`\n"
                f"🔑 *Password*: `{password}`\n"
                f"📧 *Correo*: `{correo}`\n"
                f"🔒 *Contraseña correo*: `{pass_correo}`\n"
                f"🌍 *País*: `{pais_text}`\n\n"
                f"Reporta el estado usando los botones abajo:",
                parse_mode="Markdown",
                reply_markup=reply_markup,
            )
            return

    await update.message.reply_text("❌ No quedan cuentas libres disponibles (evitando LATAM).")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_name = query.from_user.username
    if not user_name:
        user_name = query.from_user.first_name

    action, cuenta_reportada = query.data.split("|")
    filas = filas_usuario.get(user_name, [])

    for info in filas:
        if info["cuenta"] == cuenta_reportada:
            row_number = info["fila"]
            filas.remove(info)
            if action == "NO_FUNCIONA":
                await asyncio.to_thread(sheet.update_cell, row_number, COL_ESTADO, "NO_FUNCIONA")
                await asyncio.to_thread(color_fila, row_number, RED)
                await query.edit_message_text(f"⚠️ Cuenta `{cuenta_reportada}` marcada como NO FUNCIONA.")
            elif action == "LATAM":
                await asyncio.to_thread(sheet.update_cell, row_number, COL_ESTADO, "LATAM")
                await asyncio.to_thread(sheet.update_cell, row_number, COL_PAIS, "LATAM")
                await asyncio.to_thread(color_fila, row_number, YELLOW)
                await query.edit_message_text(f"🟨 Cuenta `{cuenta_reportada}` marcada como LATAM.")
            return

    await query.edit_message_text("❗ No tienes ninguna cuenta pendiente con ese nombre.")

# ============================
# INICIO DEL BOT
# ============================

def main():
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    if not TOKEN:
        raise ValueError("No se ha definido la variable de entorno TELEGRAM_TOKEN")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pedir_cuenta", pedir_cuenta))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("🤖 Bot funcionando…")
    app.run_polling()

if __name__ == "__main__":
    main()
