#!/bin/bash
# One-shot reminder; unloads itself after sending.
TOKEN=$(security find-generic-password -s apple-buyer -a telegram_bot_token -w)
CHAT=$(security find-generic-password -s apple-buyer -a telegram_chat_id -w)
curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" -d chat_id="$CHAT" --data-urlencode text="Reminder: your virtual card for the iPhone Duo bot expires ~9pm tonight. Text Claude on the Mac mini the new card details (number, expiry, CVV)." >/dev/null
launchctl bootout gui/$(id -u)/com.usaid.apple-buyer.remind 2>/dev/null
rm -f ~/Library/LaunchAgents/com.usaid.apple-buyer.remind.plist
