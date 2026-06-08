from payment_bot.ui.keyboards import payment_action_kb


def payment_link_kb(url: str):
    return payment_action_kb(url)
