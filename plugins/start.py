
import asyncio
import humanize

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from pyrogram.errors import (
    FloodWait,
    UserIsBlocked,
    InputUserDeactivated,
)

from bot import Bot
from config import (
    ADMINS,
    FORCE_MSG,
    START_MSG,
    DISABLE_CHANNEL_BUTTON,
    PROTECT_CONTENT,
    FILE_AUTO_DELETE,
)
from helper_func import (
    subscribed,
    decode,
    get_messages,
    get_missing_channels,
)
from database.database import (
    add_user,
    del_user,
    full_userbase,
    present_user,
)


file_auto_delete = humanize.naturaldelta(FILE_AUTO_DELETE)


@Bot.on_message(
    filters.command("start") & filters.private & subscribed
)
async def start_command(client: Client, message):
    user_id = message.from_user.id

    if not await present_user(user_id):
        try:
            await add_user(user_id)
        except Exception as e:
            print(f"Add user error: {e}")

    text = message.text or ""

    if len(text) > 7:
        try:
            base64_string = text.split(" ", 1)[1]
            decoded_string = await decode(base64_string)
            argument = decoded_string.split("-")

            if len(argument) == 3:
                start = int(
                    int(argument[1]) / abs(client.db_channel.id)
                )
                end = int(
                    int(argument[2]) / abs(client.db_channel.id)
                )

                if start <= end:
                    ids = range(start, end + 1)
                else:
                    ids = range(start, end - 1, -1)

            elif len(argument) == 2:
                file_id = int(
                    int(argument[1]) / abs(client.db_channel.id)
                )
                ids = [file_id]

            else:
                await message.reply_text("Invalid file link.")
                return

        except Exception as e:
            print(f"File link error: {e}")
            await message.reply_text("Invalid or expired file link.")
            return

        temp_msg = await message.reply_text("Please wait...")

        try:
            messages = await get_messages(client, ids)

        except Exception as e:
            print(f"Get messages error: {e}")
            await temp_msg.delete()
            await message.reply_text("Something went wrong!")
            return

        await temp_msg.delete()

        sent_messages = []

        for msg in messages:
            # Remove all old captions.
            caption = ""

            if DISABLE_CHANNEL_BUTTON:
                reply_markup = msg.reply_markup
            else:
                reply_markup = None

            try:
                sent_msg = await msg.copy(
                    chat_id=user_id,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                    protect_content=PROTECT_CONTENT,
                )

                sent_messages.append(sent_msg)

            except FloodWait as e:
                await asyncio.sleep(e.value)

                try:
                    sent_msg = await msg.copy(
                        chat_id=user_id,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup,
                        protect_content=PROTECT_CONTENT,
                    )

                    sent_messages.append(sent_msg)

                except Exception as retry_error:
                    print(f"Retry send error: {retry_error}")

            except Exception as e:
                print(f"File send error: {e}")

        # IMPORTANT message + More Videos button in the same message.
        more_videos_keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "▶️ More Videos",
                        url="https://t.me/Malluxix",
                    )
                ]
            ]
        )

        info_message = await client.send_message(
            chat_id=user_id,
            text="ㅤㅤㅤ❕⌠  𝘐𝘔𝘗𝘖𝘙𝘛𝘈𝘕𝘛 ⌡ ❕",
            reply_markup=more_videos_keyboard,
        )

        # Keep automatic file deletion.
        asyncio.create_task(
            delete_files(
                sent_messages,
                client,
            )
        )

        return

    # Normal /start welcome message.
    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "😊 About Me",
                    callback_data="about",
                ),
                InlineKeyboardButton(
                    "🔒 Close",
                    callback_data="close",
                ),
            ]
        ]
    )

    await message.reply_text(
        text=START_MSG.format(
            first=message.from_user.first_name,
            last=message.from_user.last_name,
            username=(
                None
                if not message.from_user.username
                else "@" + message.from_user.username
            ),
            mention=message.from_user.mention,
            id=user_id,
        ),
        reply_markup=reply_markup,
        disable_web_page_preview=True,
        quote=True,
    )


@Bot.on_message(
    filters.command("start") & filters.private
)
async def not_joined(client: Client, message):
    missing_channels = await get_missing_channels(
        client,
        message.from_user.id,
    )

    buttons = []

    for i, channel_id in enumerate(missing_channels, start=1):
        link = client.invitelinks.get(channel_id)

        if link:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"Join Channel {i}",
                        url=link,
                    )
                ]
            )

    if len(message.command) > 1:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="Try Again",
                    url=(
                        f"https://t.me/{client.username}"
                        f"?start={message.command[1]}"
                    ),
                )
            ]
        )

    await message.reply(
        text=FORCE_MSG.format(
            first=message.from_user.first_name,
            last=message.from_user.last_name,
            username=(
                None
                if not message.from_user.username
                else "@" + message.from_user.username
            ),
            mention=message.from_user.mention,
            id=message.from_user.id,
        ),
        reply_markup=InlineKeyboardMarkup(buttons),
        quote=True,
        protect_content=True,
        disable_web_page_preview=True,
    )


@Bot.on_message(
    filters.command("users")
    & filters.private
    & filters.user(ADMINS)
)
async def get_users(client: Bot, message):
    msg = await client.send_message(
        chat_id=message.chat.id,
        text="Processing...",
    )

    users = await full_userbase()

    await msg.edit(
        f"{len(users)} Users Are Using This Bot"
    )


@Bot.on_message(
    filters.private
    & filters.command("broadcast")
    & filters.user(ADMINS)
)
async def send_text(client: Bot, message):
    if not message.reply_to_message:
        msg = await message.reply_text(
            "Reply to a message to broadcast it."
        )
        await asyncio.sleep(8)
        await msg.delete()
        return

    users = await full_userbase()
    broadcast_msg = message.reply_to_message

    total = 0
    successful = 0
    blocked = 0
    deleted = 0
    unsuccessful = 0

    progress = await message.reply_text(
        "Broadcasting message... Please wait."
    )

    for chat_id in users:
        total += 1

        try:
            await broadcast_msg.copy(chat_id)
            successful += 1

        except FloodWait as e:
            await asyncio.sleep(e.value)

            try:
                await broadcast_msg.copy(chat_id)
                successful += 1
            except Exception:
                unsuccessful += 1

        except UserIsBlocked:
            await del_user(chat_id)
            blocked += 1

        except InputUserDeactivated:
            await del_user(chat_id)
            deleted += 1

        except Exception as e:
            print(f"Broadcast error for {chat_id}: {e}")
            unsuccessful += 1

    status = (
        "<b><u>Broadcast Completed</u></b>\n\n"
        f"<b>Total Users:</b> <code>{total}</code>\n"
        f"<b>Successful:</b> <code>{successful}</code>\n"
        f"<b>Blocked Users:</b> <code>{blocked}</code>\n"
        f"<b>Deleted Accounts:</b> <code>{deleted}</code>\n"
        f"<b>Unsuccessful:</b> <code>{unsuccessful}</code>"
    )

    await progress.edit_text(status)


async def delete_files(messages, client):
    await asyncio.sleep(FILE_AUTO_DELETE)

    for msg in messages:
        try:
            await client.delete_messages(
                chat_id=msg.chat.id,
                message_ids=msg.id,
            )

        except Exception as e:
            print(
                f"Could not delete message {msg.id}: {e}"
            )


# Existing project credits retained.
# Jishu Developer
# Telegram Channel @Madflix_Bots
# Backup Channel @JishuBotz
# Developer @JishuDeveloper
