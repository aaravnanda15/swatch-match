# Before and after: the same five chats

Before = commit 5a7f844 (fixed templates). After = this code (the AI writes the reply, checked against stock.csv). Made by `scripts/demo_conversations.py`. In this run Gemini's daily free quota ran out after the first chat, so most "after" replies are the warm templates (the fallback), not AI-written.

## Ramesh Textiles (Hinglish wedding order)

| Buyer | Before | After |
|---|---|---|
| laal bandhani saree chahiye shaadi ke liye | Namaste ji 🙏 Yeh designs abhi available hain:<br><br>1. Gold Kanchi Silk Saree (D003): ₹1,450 per piece, 8 stock mein<br>2. Orange Georgette Bandhani Dupatta (D024): ₹4,100 per piece, 3 stock mein<br>3. Purple Bandhani Dupatta, Red Pallu (D017): ₹1,250 per piece, 20 stock mein<br><br>Kitne piece chahiye?<br>(Photo mein colour thoda alag dikh sakta hai.) | Namaste Ramesh ji, shaadi ke liye laal bandhani saree ki maang par yeh designs available hain:<br><br>1. Gold Kanchi Silk Saree (D003): ₹1,450 per piece, 8 stock mein<br>2. Orange Georgette Bandhani Dupatta (D024): ₹4,100 per piece, 3 stock mein<br>3. Purple Bandhani Dupatta, Red Pallu (D017): ₹1,250 per piece, 20 stock mein<br><br>Laal saree ke kitne piece rakh doon aapke liye? (Photo mein colour thoda alag dikh sakta hai.)<br>_AI, checked_ |
| 30 piece | D003 ke abhi sirf 8 piece hain. Saare 8 le lenge, ya milte-julte design dikhayein? | Shaadi ke liye 30 piece ek saath mushkil hoga kyunki D003 abhi sirf 8 piece stock mein hai. Saare 8 lenge, ya aur design dekhenge?<br>_AI, checked_ |
| haan | Ho gaya! Gold Kanchi Silk Saree (D003) ke 8 piece note kar liye. Details thodi der mein bhejte hain 🙏 | Shaadi ke liye laal bandhani ke baad yeh bhi badhiya rahega. Ho gaya! Gold Kanchi Silk Saree (D003) ke 8 piece note kar liye. Details thodi der mein bhejte hain 🙏<br>_AI, checked_ |

## Patel Fabrics (Gujarati, unit mix-up)

| Buyer | Before | After |
|---|---|---|
| લાલ ઇકત કાપડ જોઈએ છે | નમસ્તે 🙏 આ ડિઝાઇન હાલ ઉપલબ્ધ છે:<br><br>1. Red Silk Ikat Fabric (D019): ₹2,850 પ્રતિ પીસ, 3 સ્ટોકમાં<br>2. Brown Ikat Cotton Fabric (D004): ₹4,050 પ્રતિ પીસ, 3 સ્ટોકમાં<br><br>કેટલા પીસ જોઈએ?<br>(ફોટામાં રંગ થોડો અલગ લાગી શકે.) | નમસ્તે Patel જી 🙏 આ ડિઝાઇન હાલ ઉપલબ્ધ છે:<br><br>1. Red Silk Ikat Fabric (D019): ₹2,850 પ્રતિ પીસ, 3 સ્ટોકમાં<br>2. Brown Ikat Cotton Fabric (D004): ₹4,050 પ્રતિ પીસ, 3 સ્ટોકમાં<br><br>કેટલા પીસ જોઈએ?<br>(ફોટામાં રંગ થોડો અલગ લાગી શકે.)<br>_template_ |
| ૨૦ કિલો | કાપડ પીસમાં મળે છે, કિલોમાં નહીં. શું તમને લાલ કાપડ ના 20 પીસ જોઈએ છે? | અમે કાપડ પીસમાં આપીએ છીએ, કિલોમાં નહીં. 20 પીસ જોઈએ છે?<br>_template_ |
| હા | D019 ના હાલ ફક્ત 3 પીસ છે. બધા 3 લેશો, કે મળતી ડિઝાઇન બતાવીએ? | D019 ના હાલ ફક્ત 3 પીસ છે. બધા 3 લેશો, કે મળતી ડિઝાઇન બતાવીએ?<br>_template_ |

## Anita (delivery and COD)

| Buyer | Before | After |
|---|---|---|
| blue dupatta | Namaste 🙏 Here's what we have for you:<br><br>1. Blue Cotton Bandhani Dupatta (D016): ₹1,950 a piece, 5 in stock<br>2. Blue Silk Bandhani Dupatta (D010): ₹4,050 a piece, 8 in stock<br>3. Purple Bandhani Dupatta, Red Pallu (D017): ₹1,250 a piece, 20 in stock<br><br>How many pieces would you like?<br>(Colours can look a little different on a phone screen.) | Namaste Anita ji 🙏 Here's what we have:<br><br>1. Blue Cotton Bandhani Dupatta (D016): ₹1,950 a piece, 5 in stock<br>2. Blue Silk Bandhani Dupatta (D010): ₹4,050 a piece, 8 in stock<br>3. Purple Bandhani Dupatta, Red Pallu (D017): ₹1,250 a piece, 20 in stock<br><br>How many pieces would you like?<br>(Colours can look a little different on a phone screen.)<br>_template_ |
| delivery to Surat? | Sorry, I didn't quite get that. How many pieces of the blue dupatta would you like? | We deliver across India by courier or transport, usually in 4 to 7 days. How many pieces do you need?<br>_template_ |
| COD? | We only deal in sarees, dupattas and fabric here. How many pieces of the blue dupatta would you like? | We take UPI or bank transfer, paid in full before dispatch. We don't do cash on delivery. How many pieces would you like?<br>_template_ |
| 10 pcs | We only have 5 pieces of D016 right now. Would you like all 5, or shall I show you a few similar designs? | Sorry Anita ji, D016 has only 5 pieces left. Shall I keep all 5 for you, or show you similar designs?<br>_template_ |

## Kavita Boutique (turns down two designs)

| Buyer | Before | After |
|---|---|---|
| red saree? | Namaste 🙏 Here's what we have for you:<br><br>1. Gold Kanchi Silk Saree (D003): ₹1,450 a piece, 8 in stock<br><br>How many pieces would you like?<br>(Colours can look a little different on a phone screen.) | Namaste Kavita ji 🙏 Here's what we have:<br><br>1. Gold Kanchi Silk Saree (D003): ₹1,450 a piece, 8 in stock<br><br>How many pieces would you like?<br>(Colours can look a little different on a phone screen.)<br>_template_ |
| not this one, show another | Sorry, I didn't quite get that. How many pieces of the red saree would you like? | Stock as of now:<br>• D013 Multicolour Jamdani Saree: 12 in stock, ₹600 a piece<br>• D019 Red Silk Ikat Fabric: 3 in stock, ₹2,850 a piece<br>• D012 Maroon Patan Patola Saree: 50 in stock, ₹4,350 a piece How many pieces of the red saree do you need?<br>_template_ |
| no, another one | We only deal in sarees, dupattas and fabric here. How many pieces of the red saree would you like? | Here's the stock right now:<br>• D019 Red Silk Ikat Fabric: 3 in stock, ₹2,850 a piece<br>• D012 Maroon Patan Patola Saree: 50 in stock, ₹4,350 a piece How many pieces of the red saree would you like?<br>_template_ |
| the first one | No problem. Message us whenever you're ready, we're happy to help 🙏 | Lovely pick! How many pieces of the Red Silk Ikat Fabric (D019) shall I keep for you?<br>_template_ |

## Sunil Traders (rude, then a real question)

| Buyer | Before | After |
|---|---|---|
| yo bro | Sorry, I didn't quite get that. What are you looking for today? A photo, the colour or the type (saree, dupatta) is enough. | Sorry, I didn't quite get that. Tell me what you have in mind Sunil ji. A photo, a colour or the type (saree, dupatta) is enough.<br>_template, can wait_ |
| wtf | We only deal in sarees, dupattas and fabric here. What are you looking for today? A photo, the colour or the type (saree, dupatta) is enough. | We only deal in sarees, dupattas and fabric here. What can I find for you? Send a photo, or tell me the colour and type (saree, dupatta).<br>_template, can wait_ |
| ok sorry, is it pure silk? | Namaste 🙏 Here's what we have for you:<br><br>1. Gold Kanchi Silk Saree (D003): ₹1,450 a piece, 8 in stock<br>2. Blue Silk Bandhani Dupatta (D010): ₹4,050 a piece, 8 in stock<br>3. Purple Raw Silk Fabric (D029): ₹1,200 a piece, 8 in stock<br><br>How many pieces would you like?<br>(Colours can look a little different on a phone screen.) | Good question Sunil ji. Let me check with the owner and get back to you shortly. What are you looking for today? A photo, the colour or the type (saree, dupatta) is enough.<br>_template_ |