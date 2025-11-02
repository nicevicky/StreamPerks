import axios from "axios";

export default async function handler(req, res) {
  try {
    if (req.method !== "POST") {
      return res.status(200).send("✅ StreamPerks Bot is LIVE on Vercel!");
    }

    const body = req.body;
    const TELEGRAM_TOKEN = process.env.BOT_TOKEN;
    const API_URL = `https://api.telegram.org/bot${TELEGRAM_TOKEN}`;
    const WEB_APP_URL = process.env.WEB_APP_URL || "https://stream-perks.vercel.app/";

    // ✅ MOVED UP: Handle callback queries (button clicks) FIRST
    if (body.callback_query) {
      const callbackQuery = body.callback_query;
      const callbackChatId = callbackQuery.message.chat.id;
      const callbackData = callbackQuery.data;
      const callbackUser = callbackQuery.from;

      switch (callbackData) {
        case "allow_messages":
          await axios.post(`${API_URL}/answerCallbackQuery`, {
            callback_query_id: callbackQuery.id,
            text: 'You have allowed the bot to send you messages!',
            show_alert: true
          });

          await axios.post(`${API_URL}/sendMessage`, {
            chat_id: callbackChatId,
            text: '✅ Thanks for allowing me to send you messages! You\'ll receive important updates and rewards notifications.'
          });
          break;

        case "how_it_works":
          await axios.post(`${API_URL}/answerCallbackQuery`, {
            callback_query_id: callbackQuery.id,
            text: "Loading..."
          });

          await axios.post(`${API_URL}/sendMessage`, {
            chat_id: callbackChatId,
            text: `
📚 <b>How StreamPerks Works</b>

<b>1️⃣ Get Started</b>
    • Register and receive welcome bonus
    • Complete your profile setup
    • Claim daily login rewards

<b>2️⃣ Complete Tasks</b>
    • Social media tasks
    • Watch video tasks
    • Visit partner links
    • Earn tokens for each completion! 💰

<b>3️⃣ Watch Ads</b>
    • View sponsored advertisements
    • Earn rewards instantly
    • Multiple ad networks supported
    
<b>4️⃣ Daily Bonuses</b>
    • Login daily for rewards
    • Build streak for bigger bonuses
    • Max streak bonus up to 5x! 🔥

<b>5️⃣ Invite Friends</b>
    • Share your referral link
    • Earn bonus for each friend
    • Unlimited earning potential! 👥

<b>6️⃣ Withdraw Earnings</b>
    • Multiple crypto options
    • Fast and secure payouts
    • Direct to your wallet! 🔐

<b>Ready to start earning?</b> Tap below! 👇
            `,
            parse_mode: "HTML",
            reply_markup: {
              inline_keyboard: [
                [
                  {
                    text: "🚀 Launch StreamPerks",
                    web_app: { url: WEB_APP_URL }
                  }
                ],
                [
                  { text: "👥 Invite Friends", callback_data: "invite" },
                  { text: "❓ Help", callback_data: "help" }
                ]
              ]
            }
          });
          break;

        case "help":
          await axios.post(`${API_URL}/answerCallbackQuery`, {
            callback_query_id: callbackQuery.id,
            text: "Loading..."
          });

          await axios.post(`${API_URL}/sendMessage`, {
            chat_id: callbackChatId,
            text: `
❓ <b>Need Help?</b>

<b>Common Questions:</b>

<b>Q: How do I earn tokens?</b>
A: Complete tasks, watch ads, claim daily bonuses, and invite friends!

<b>Q: What is daily streak bonus?</b>
A: Login daily to increase your streak multiplier (up to 5x base bonus).

<b>Q: How do withdrawals work?</b>
A: Go to "Withdraw" → Select crypto → Enter amount & wallet → Submit!

<b>Q: What's the referral bonus?</b>
A: You earn bonus tokens when friends join using your link!

<b>Q: How do I complete tasks?</b>
A: Go to "Tasks" tab → Click task → Complete action → Verify → Get rewarded!

<b>Q: Is it safe?</b>
A: Yes! We use secure blockchain technology and encrypted transactions.

<b>Q: What's the minimum withdrawal?</b>
A: Check settings - typically 10 tokens minimum.

<b>Still need help?</b>
📧 Support: @YourSupportUsername
💬 Community: @StreamPerksChat
            `,
            parse_mode: "HTML",
            reply_markup: {
              inline_keyboard: [
                [
                  {
                    text: "🚀 Launch App",
                    web_app: { url: WEB_APP_URL }
                  }
                ],
                [
                  { text: "📖 How it Works", callback_data: "how_it_works" }
                ]
              ]
            }
          });
          break;

        case "invite":
          await axios.post(`${API_URL}/answerCallbackQuery`, {
            callback_query_id: callbackQuery.id,
            text: "Loading..."
          });

          // Get bot username
          const botInfo = await axios.get(`${API_URL}/getMe`);
          const botUsername = botInfo.data.result.username;
          const inviteLink = `https://t.me/${botUsername}/Perks?startapp=${callbackUser.id}`;

          await axios.post(`${API_URL}/sendMessage`, {
            chat_id: callbackChatId,
            text: `
👥 <b>Invite Friends & Earn Together!</b>

Share your personal referral link:
<code>${inviteLink}</code>

💰 <b>Your Rewards:</b>
✅ Bonus tokens for each friend who joins
✅ Your friend gets welcome bonus too
✅ Unlimited referrals = Unlimited earnings!
✅ Track all referrals in your dashboard

📱 <b>How to Share:</b>
1. Tap "Share Link" below
2. Send to friends on Telegram
3. Earn when they register! 🚀

<b>📊 Referral Benefits:</b>
• Instant bonus on friend signup
• Bonus amount shown in settings
• Real-time tracking
• Transparent transaction history

<i>The more you share, the more you earn! 💎</i>
            `,
            parse_mode: "HTML",
            reply_markup: {
              inline_keyboard: [
                [
                  {
                    text: "📤 Share Referral Link",
                    url: `https://t.me/share/url?url=${encodeURIComponent(
                      inviteLink
                    )}&text=${encodeURIComponent(
                      "🚀 Join me on StreamPerks and start earning tokens daily! Complete tasks, watch ads, and get rewards! Free registration bonus awaiting! 💰✨"
                    )}`
                  }
                ],
                [
                  {
                    text: "📊 Open My Dashboard",
                    web_app: { url: WEB_APP_URL }
                  }
                ],
                [
                  { text: "📖 How it Works", callback_data: "how_it_works" }
                ]
              ]
            }
          });
          break;

        case "stats":
          await axios.post(`${API_URL}/answerCallbackQuery`, {
            callback_query_id: callbackQuery.id,
            text: "Opening your stats..."
          });

          await axios.post(`${API_URL}/sendMessage`, {
            chat_id: callbackChatId,
            text: `
📊 <b>Your StreamPerks Stats</b>

To view your complete statistics:
• Total balance
• Total earned
• Total withdrawn
• Referral count
• Daily streak
• Transaction history

👇 <b>Open the app below:</b>
            `,
            parse_mode: "HTML",
            reply_markup: {
              inline_keyboard: [
                [
                  {
                    text: "📊 View Full Stats",
                    web_app: { url: WEB_APP_URL }
                  }
                ]
              ]
            }
          });
          break;

        default:
          await axios.post(`${API_URL}/answerCallbackQuery`, {
            callback_query_id: callbackQuery.id
          });
          break;
      }

      return res.status(200).end();
    }

    // ✅ Handle regular messages SECOND
    if (body.message) {
      const chatId = body.message.chat.id;
      const user = body.message.from;
      const text = body.message.text || "";

      // ✅ Extract start parameter (if exists)
      let startParam = null;
      let referrerId = null;

      if (text.startsWith("/start ")) {
        startParam = text.replace("/start ", "").trim();

        // Parse referral ID from different formats
        if (startParam.includes("startapp=")) {
          referrerId = startParam.split("startapp=")[1];
        } else if (startParam) {
          referrerId = startParam;
        }
      }

      // ✅ Handle /start with referral parameter (from deep link)
      if (text.startsWith("/start ") && referrerId) {
        const welcomeMessage = `
🎉 <b>Welcome to StreamPerks!</b> 🎉

Hi <b>${user.first_name}</b>! 👋

You've been invited to join our earning community!

✨ <b>What you'll receive:</b>
💰 Registration bonus
🎯 Task completion rewards
📺 Ad viewing rewards
📅 Daily login bonuses
👥 Referral rewards system

🎁 <b>Special Offer:</b>
You were invited by User ID: <code>${referrerId}</code>
Both of you will receive <b>referral bonus rewards</b>! 🎊

⚡️ <b>Get Started in 3 Steps:</b>
1️⃣ Tap "Launch App" below
2️⃣ Complete your first task
3️⃣ Start earning immediately!

<b>💎 Multiple Ways to Earn:</b>
• Complete social tasks
• Watch sponsored ads
• Daily login streaks
• Invite friends
• Special events & bonuses

<i>Join thousands earning tokens daily! 🚀</i>
        `.trim();

        await axios.post(`${API_URL}/sendMessage`, {
          chat_id: chatId,
          text: welcomeMessage,
          parse_mode: "HTML",
          reply_markup: {
            inline_keyboard: [
              [
                {
                  text: "🚀 Launch StreamPerks App",
                  web_app: { url: `${WEB_APP_URL}?startapp=${referrerId}` }
                }
              ],
              [
                { text: "📊 How it Works", callback_data: "how_it_works" },
                { text: "❓ Help", callback_data: "help" }
              ],
              [
                { text: "👥 My Referral Link", callback_data: "invite" }
              ]
            ]
          }
        });

        // Optional: Send a follow-up sticker/animation for engagement
        await axios
          .post(`${API_URL}/sendSticker`, {
            chat_id: chatId,
            sticker: "CAACAgIAAxkBAAEMYgBmVxZ3Y..." // Replace with your sticker file_id
          })
          .catch(() => {}); // Silent fail if sticker doesn't work

        return res.status(200).end();
      }

      // ✅ Handle normal /start (no parameters)
      if (text === "/start") {
        const message = `
<b>🚀 Welcome to StreamPerks!</b>

💠 <b>Top-Rated Earning Platform</b> in Telegram
💠 <b>Multiple Earning Methods</b>
💠 Tasks | Ads | Daily Bonuses | Referrals
💠 Available Worldwide 🌍
💠 Instant Payouts | Secure Withdrawals 💸

<b>🎁 New User Benefits:</b>
✅ Registration bonus
✅ Welcome tasks bundle
✅ Daily streak rewards
✅ Referral program access

<b>💰 Earning Methods:</b>
🎯 Complete Tasks - Social media & links
📺 Watch Ads - Instant rewards
📅 Daily Bonuses - Build your streak
👥 Invite Friends - Unlimited earnings

🔥 <b>Start earning in 30 seconds!</b> 👇
        `.trim();

        await axios.post(`${API_URL}/sendMessage`, {
          chat_id: chatId,
          text: message,
          parse_mode: "HTML",
          reply_markup: {
            inline_keyboard: [
              [
                {
                  text: "⚡ Start Earning Now",
                  web_app: { url: WEB_APP_URL }
                }
              ],
              [
                { text: "📖 How it Works", callback_data: "how_it_works" },
                { text: "👥 Invite Friends", callback_data: "invite" }
              ],
              [
                { text: "❓ Help & FAQ", callback_data: "help" }
              ]
            ]
          }
        });

        return res.status(200).end();
      }

      // ✅ Handle /help command
      if (text === "/help") {
        await axios.post(`${API_URL}/sendMessage`, {
          chat_id: chatId,
          text: "❓ Loading help information...",
          parse_mode: "HTML"
        });
        
        // Trigger help callback
        return res.status(200).end();
      }

      // ✅ Handle /stats command
      if (text === "/stats") {
        await axios.post(`${API_URL}/sendMessage`, {
          chat_id: chatId,
          text: `
📊 <b>View Your Stats</b>

Open the app to see:
• Current balance
• Total earned
• Withdrawal history
• Referral statistics
• Daily streak progress

👇 Tap below to view full dashboard:
          `,
          parse_mode: "HTML",
          reply_markup: {
            inline_keyboard: [
              [
                {
                  text: "📊 Open Dashboard",
                  web_app: { url: WEB_APP_URL }
                }
              ]
            ]
          }
        });
        return res.status(200).end();
      }

      // ✅ Handle /invite command
      if (text === "/invite") {
        const botInfo = await axios.get(`${API_URL}/getMe`);
        const botUsername = botInfo.data.result.username;
        const inviteLink = `https://t.me/${botUsername}/Perks?startapp=${user.id}`;

        await axios.post(`${API_URL}/sendMessage`, {
          chat_id: chatId,
          text: `
👥 <b>Your Referral Link:</b>

<code>${inviteLink}</code>

Tap "Share Link" below to invite friends! 💰
          `,
          parse_mode: "HTML",
          reply_markup: {
            inline_keyboard: [
              [
                {
                  text: "📤 Share Link",
                  url: `https://t.me/share/url?url=${encodeURIComponent(
                    inviteLink
                  )}&text=${encodeURIComponent(
                    "🚀 Join me on StreamPerks! Earn tokens by completing tasks, watching ads, and inviting friends! 💰"
                  )}`
                }
              ]
            ]
          }
        });
        return res.status(200).end();
      }

      // ✅ If it's a message but not a recognized command, send help
      if (text && text.startsWith("/")) {
        await axios.post(`${API_URL}/sendMessage`, {
          chat_id: chatId,
          text: `
❓ Unknown command. 

<b>Available Commands:</b>
/start - Launch the app
/help - Get help
/stats - View your statistics
/invite - Get your referral link

Or tap below to open the app:
          `,
          parse_mode: "HTML",
          reply_markup: {
            inline_keyboard: [
              [
                {
                  text: "🚀 Open StreamPerks",
                  web_app: { url: WEB_APP_URL }
                }
              ]
            ]
          }
        });
        return res.status(200).end();
      }

      return res.status(200).end();
    }

    // If it's not a callback or a message, end
    res.status(200).end();
    
  } catch (err) {
    console.error("Bot Error:", err.response?.data || err.message);
    res.status(500).send("Server Error");
  }
}
