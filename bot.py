from telegram import WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import pymongo  
import requests
import json
from telegram.ext import CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


client = pymongo.MongoClient("mongodb+srv://dbUser:dbUserpass@telegrambot.yngj8.mongodb.net/ReferralBotDB?retryWrites=true&w=majority")  # Replace with your connection string
db = client["ReferralBotDB"]
referrals_collection = db["Referrals"]

async def start(update, context):
    # Extract username and user ID
    username = update.message.from_user.username or "there"
    user_id = update.message.from_user.id
    context.user_data["user_id"] = user_id

    # Register user in the external database
    register_message = await register_user(user_id, username)
    print(register_message)  # Log the registration response

    # Check for referral ID in the command
    args = context.args if context.args else []
    referral_id = args[0] if args else None

    if referral_id:
        # Process the referral
        referring_user = referrals_collection.find_one({"referral_id": referral_id})

        if referring_user:
            # Check if this user is already referred
            if any(ref["referredUserId"] == str(user_id) for ref in referring_user["referrals"]):
                await update.message.reply_text("You have already been referred by this user.")
            else:
                # Add the new user to the referring user's referrals
                referring_user["referrals"].append({
                    "referredUserId": str(user_id),
                    "referredUsername": username,
                    "reward": 250,
                    "isClaimed": False
                })
                referrals_collection.update_one(
                    {"referral_id": referral_id},
                    {"$set": {"referrals": referring_user["referrals"]}}
                )

                # Notify the referring user
                referral_message = (
                    f"Hey @{referring_user['username']}, "
                    f"this referred user @{username} has used your link to start the Roaster Bot App. "
                    f"Claim 250 Rst for inviting your friend."
                )
                claim_button = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Claim 250 Rst", callback_data=f"claim_reward:{referral_id}")]
                ])
                try:
                    await context.bot.send_message(
                        chat_id=int(referral_id),
                        text=referral_message,
                        reply_markup=claim_button
                    )
                except Exception as e:
                    print(f"Failed to notify referral ID {referral_id}: {e}")

                await update.message.reply_text(f"Thank you for joining through referral ID {referral_id}!")
        else:
            await update.message.reply_text(f"Invalid referral ID: {referral_id}. Proceeding without referral.")

    # Add the new user to the local MongoDB if they don't already exist
    if not referrals_collection.find_one({"referral_id": str(user_id)}):
        referrals_collection.insert_one({
            "referral_id": str(user_id),
            "username": username,
            "referrals": []
        })

    # Provide the user with the main menu
    keyboard = [[KeyboardButton("Start Playing")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        f"Hey @{username}, welcome to Roaster Bot where you can perform multiple tasks to earn!",
        reply_markup=reply_markup
    )



# Helper function to register a user
async def register_user(user_id, username):
    url = "https://sunday-mini-telegram-bot.onrender.com/api/users/register"
    headers = {"Content-Type": "application/json"}
    payload = {
        "user_id": user_id,
        "username": username
    }

    try:
        # Send POST request to register user
        response = requests.post(url, headers=headers, json=payload)
        response_data = response.json()  # Parse the JSON response

        if response.status_code == 200:
            return response_data.get("message", "User registered successfully")
        else:
            return response_data.get("error", "Failed to register user")
    except requests.exceptions.RequestException as e:
        print(f"Error registering user: {e}")
        return "An error occurred while registering the user"


async def claim_reward(update, context):
    query = update.callback_query
    await query.answer()  # Acknowledge the callback query

    # Extract referral ID from callback data
    data = query.data.split(":")
    if len(data) != 2 or data[0] != "claim_reward":
        await query.message.reply_text("Invalid action.")
        return

    referral_id = data[1]

    # Update the referral ID's balance
    try:
        response = requests.put(
            f"https://sunday-mini-telegram-bot.onrender.com/api/users/{referral_id}/balance",
            json={"amount": 250}
        )
        if response.status_code == 200:
            balance = response.json().get("balance", 0)
            await context.bot.send_message(
                chat_id=int(referral_id),
                text=f"Well done @{query.from_user.username}, 250 Rst has been added to your balance. "
                     f"Keep up the good work and invite more friends to earn more!"
            )
            await query.message.edit_text("Reward claimed successfully!")
        else:
            await query.message.edit_text("Failed to claim reward. Please try again later.")
    except Exception as e:
        print(f"Error claiming reward for {referral_id}: {e}")
        await query.message.edit_text("An error occurred while claiming the reward.")



async def button_handler(update, context):
    user_id = update.effective_user.id
    mini_app_url = f'https://new-mini-telegram-bot.onrender.com?user_id={user_id}'

    web_app = WebAppInfo(url=mini_app_url)

    keyboard = [[KeyboardButton(
        text="Open Roaster App 🚀",
        web_app=web_app
    )]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Here you go! Click the button below to start earning:",
        reply_markup=reply_markup
    )


def main():
    app = Application.builder().token("7938728660:AAFg3Ul2k8GO2avvwhCX7OLlzvyXgQj6YEI").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(claim_reward, pattern="^claim_reward:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))

    app.run_polling()


if __name__ == '__main__':
    main()