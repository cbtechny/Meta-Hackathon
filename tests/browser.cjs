// The public site is now the single chat homepage.
if (!process.env.COUNTERPILOT_CHAT_URL && process.env.COUNTERPILOT_URL) process.env.COUNTERPILOT_CHAT_URL = process.env.COUNTERPILOT_URL;
require('./chat-browser.cjs');
