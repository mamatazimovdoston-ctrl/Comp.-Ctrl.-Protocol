# Sud Suhbat Bayonnomasi Bot

Asl Word namunasi asosida o‘zbek tilida Telegram bot. 7 bosqich, alohida maydonlarni tahrirlash, foto yoki JPG/PNG hujjat qabul qilish, DOCX va LibreOffice PDF yuborish. Token kodga yozilmaydi.

## Eng oson ishga tushirish — GitHub va Railway

1. Telegramda **@BotFather** ni oching, `/newbot` yuboring. Bot nomini va `bot` bilan tugaydigan noyob username ni tanlang. Berilgan tokenni maxfiy saqlang.
2. Loyiha GitHub repozitoriysida bo‘lsa, Railway (https://railway.com) hisobingizga kiring. **New Project → Deploy from GitHub repo** ni bosing, shu repozitoriyni tanlang. Xususiy repo ko‘rinmasa, Railway GitHub ilovasiga shu repo uchun ruxsat bering.
3. Xizmatning **Variables** bo‘limida `BOT_TOKEN` yarating va BotFather tokenini kiriting. Ixtiyoriy `ALLOWED_USER_IDS=123456789,987654321` bilan kirishni cheklang; bo‘sh bo‘lsa barcha foydalanuvchilar foydalanadi.
4. Railway Dockerfile orqali Python va LibreOffice ni o‘rnatadi. O‘zgarishlar uchun **Deploy** ni bosing. **Settings → Deploy → Replicas** qiymati **1** bo‘lsin. Serverless/App Sleeping yoqilgan bo‘lsa o‘chiring: polling bot doim ishlashi kerak.
5. **Logs** bo‘limida xatolik yo‘qligini ko‘ring. Telegram botingizga `/start` yuboring va yangi bayonnoma yarating. Web domen, PORT, webhook va database kerak emas.
6. Railway server resurslari tarifga muvofiq haq oladi. Foydalanish limitlari va billingni hisobingizdan tekshiring. PDF yaratish uchun kamida 1 GB RAM tavsiya qilinadi.

Tokenni chatga, GitHub fayliga yoki skrinshotga joylamang. Token oshkor bo‘lsa BotFather orqali yangilang va Railway Variables qiymatini almashtiring. Ikki serverda bir token bilan botni bir vaqtda ishga tushirmang.

## Docker orqali kompyuterda

Docker Desktop o‘rnatilgan bo‘lsin. Papkada `.env.example` nusxasini `.env` deb nomlang, `BOT_TOKEN` qiymatini to‘ldiring:

```sh
docker build -t sud-bot .
docker run --rm --env-file .env sud-bot
```

## Python orqali

Python 3.12+ va LibreOffice Writer kerak. Linux Debian/Ubuntu: `sudo apt-get install libreoffice-writer fonts-liberation`. Windows/macOS: LibreOffice o‘rnating; `SOFFICE` qiymatiga bajariladigan faylning to‘liq yo‘lini yozish mumkin.

```sh
python -m venv .venv
# Linux/macOS:
. .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
# .env.example dan .env yarating va token kiriting
python bot.py
```

## Foydalanish

`/start` → Yangi bayonnoma → F.I.Sh., lavozim, sana (17.11.2026), joy, mas’ul lavozimi, mas’ul F.I.Sh., rasm. Rasmni namuna holida qoldirish mumkin. Tasdiqlash ekranida **Tahrirlash** orqali istalgan maydon, jumladan rasm alohida yangilanadi. **Bayonnomani tayyorlash** DOCX va PDF yuboradi. `/cancel` jarayonni to‘xtatadi.

Rasm 10 MB gacha, JPG/PNG, har tomoni kamida 100 px. Tasvir 2040×1080 neytral maydonga proporsiyalarni saqlab joylanadi; kesilmaydi. Telegram foto yuborishda tasvirni siqishi mumkin: sifat uchun **File/Hujjat** sifatida yuboring.

Ism 120, lavozim 260, joy 80 belgigacha. Uzoq joy nomi o‘ng katak ichida yangi qatorga o‘tishi mumkin: sana bilan yuqori qatori bir xil, ustma-ust tushmaydi. Uzun sarlavha/joy uchun mavjud bo‘sh xatboshilar oralig‘i qisqartiriladi, rasm xatboshisi bir qator oralig‘iga me’yorlanadi. Shu holatda sana-sarlavha orasidagi bo‘shliq namunadan farq qilishi mumkin. Matn kesilmaydi va kichraytirilmaydi. Rasm birinchi sahifaga sig‘masa, bot aniq xabar bilan matnni tahrirlashni so‘raydi; noto‘g‘ri PDF yuborilmaydi. Chop etishdan oldin PDFni ko‘ring.

## Shablon va format

`templates/BAYONNOMA_NAMUNA.docx` — yuklangan asl faylning o‘zgarmagan nusxasi. Generator uning 30 ta asosiy xatboshi va bitta rasmli tuzilmasini tekshiradi. Uni boshqa tuzilmadagi fayl bilan almashtirsangiz generatorni moslashtirish kerak.

- 0-xatboshi: xodim lavozimi va F.I.Sh.; runlar orasidan aniq maydon bo‘yicha almashtiriladi.
- 4-xatboshi: sana/joy chegarasiz ikki ustunli jadvalga aylanadi.
- 13-xatboshi: mavjud DrawingML rasm, 17×9 sm, markazda. Yangi rasm shu bog‘lanishda almashtiriladi.
- 16-xatboshi: suhbat haqidagi jumladagi mas’ul lavozimi, xodim lavozimi va F.I.Sh.
- 17-xatboshi: `A.Anvarov` → `Ism bosh harfi.Familiya`.
- 21–22 va 28–29-xatboshilar: chapda lavozim, o‘ngda qisqartirilgan F.I.Sh., chegarasiz imzo jadvallari.
- Qolgan barcha huquqiy xatboshilar va yakuniy ogohlantirish o‘zgarmaydi.

Asl namuna rasmi taxminan 17.14×9.15 sm. Yakuniy talabga ko‘ra maydon 17×9 sm qilib me’yorlanadi; namunani qoldirganda tasvirning o‘zi saqlanadi. `python-docx` va OOXML run formatini saqlaydi; docxtpl bog‘liqligi berilgan, ammo bu shablonda Jinja placeholderlardan foydalanish zarur emas.

Shrift nomlari saqlanadi. Dockerda Times New Roman mavjud bo‘lmasa, LibreOffice Liberation Serif bilan almashtiradi. Microsoft shriftining aniq ko‘rinishi talab qilinsa, litsenziyali Times New Roman fayllarini serverga o‘rnating. Word va LibreOffice sahifalashi ayrim uzun matnlarda farq qilishi mumkin; PDF chop etish nusxasi hisoblanadi.

## Maxfiylik va ishlash

Faqat shaxsiy chat. Har foydalanuvchi alohida RAM sessiyasi va qulfga ega. Bir vaqtda 2 ta generator, har biriga alohida vaqtinchalik papka va LibreOffice profil. Fayllar yuborish tugagach yoki xatoda diskdan o‘chadi. Tugallangan/bekor qilingan sessiya o‘chiriladi, faolsiz sessiyalar 30 daqiqadan so‘ng tozalanadi. Bot qayta ishga tushsa to‘ldirilmagan ma’lumotlar yo‘qoladi. Rasm va F.I.Sh. logga yozilmaydi. Telegramga yuborilgan hujjatlar Telegram chatida qoladi; server tozalashi ularni chatdan o‘chirmaydi.

PDF konversiyasi xato bersa Word yuboriladi va qayta urinish imkoniyati qoladi. Vaqtinchalik fayllar `finally`/context manager orqali tozalanadi. `/start` pollingni boshlaganda eski kutilayotgan yangilanishlar tashlanadi.

## Test

```sh
pip install -r requirements-dev.txt
python -m pytest -q
python tests/create_examples.py
```

Ikkinchi buyruq uchun LibreOffice kerak. U haqiqiy shablondan uchta DOCX/PDF juftligi yaratadi. `examples/` ichidagi misollar sun’iy ism va tasvirlardan iborat. TEST_REPORT.md bajarilgan tekshiruvlar va cheklovlarni ko‘rsatadi.

## AI yordamida rasmni qirqish va oldindan ko‘rish

Yangi rasm yuborilganda bot OpenCV ning o‘rgatilgan frontal va profil yuz detektorlari yordamida 17:9 qirqish variantini taklif qiladi. Model fayllari `models/` ichida, serverda mahalliy ishlaydi: foydalanuvchi surati tashqi AI xizmatiga yuborilmaydi, pullik API kaliti kerak emas. Tasvir generatsiya qilinmaydi; yuz, odam yoki buyumlar qayta chizilmaydi.

Bot avval rasmni ko‘rsatadi, keyin foydalanuvchi quyidagilardan birini tanlaydi:

- **✅ Rasmni tasdiqlash** — ko‘rsatilgan variantni hujjatda ishlatish.
- **🖼 Asl rasmni saqlash** — to‘liq suratni kesmasdan, proporsiyalarini saqlagan holda neytral fonli 17×9 sm maydonga sig‘dirish.
- **🔄 Boshqa rasm yuborish** — qayta yuklash.

Model barcha yuzlarni, qo‘llarni yoki hujjatlarni aniqlashiga kafolat yo‘q. Algoritm aniqlangan yuzlar atrofida zaxira va pastda yelka/stol uchun joy saqlaydi. Yuz topilmasa, model xato bersa yoki xavfsiz hudud sig‘masa, surat kesilmaydi. Har bir yangi surat foydalanuvchi tomonidan tasdiqlanadi. Yuborilgan preview Telegramda siqilishi mumkin, hujjatda esa sessiyadagi PNG ishlatiladi. Faol sessiyalar deploy vaqtida yo‘qolishi mumkin — `/start` bilan qayta boshlang.

Model manbasi: OpenCV 4.12.0 `data/haarcascades/haarcascade_frontalface_default.xml` va `haarcascade_profileface.xml`. Litsenziya bildirishnomalari XML fayllarning boshida saqlangan.

## Uch xil yozuv va matnni tasdiqlash

Yangi bayonnoma yaratishda avval **Lotin**, **Kirill** yoki foydalanuvchi tasdiqlagan **Yangi lotin (ŏ, ğ, ş, ç)** tanlanadi. Yangi lotin alohida foydalanuvchi varianti bo‘lib, amaldagi rasmiy alifbo sifatida da’vo qilinmaydi.

`transliteration.py` apostroflarni birxillashtiradi: o‘/g‘ uchun `‘`, tutuq belgisi uchun `ʼ`; oddiy klaviatura apostroflari va o-/g- birikmalari ham tuzatiladi. Кириллдаги `ў`, `ғ`, `ъ`, `ь`, `е` kontekstga muvofiq o‘giriladi; obyekt/subyekt, sudya va oy nomlari uchun maxsus imlo qoidalari bor. Bu deterministik transliteratsiya: to‘liq imlo tekshirgich yoki tarjimon emas. Ismlar, qo‘shma so‘zlar, ruscha so‘zlar va sh/ch/ts/ye kabi birikmalar har doim avtomatik to‘g‘ri talqin qilinmasligi mumkin. Foydalanuvchi matnni ko‘rib **Matnni tasdiqlash** tugmasini bosadi; **Tahrirlash → Yozuv turi** orqali yozuvni almashtiradi.

Tanlangan yozuv butun DOCX matniga, jumladan huquqiy xatboshilar, sana, joy, sarlavha va imzolarga qo‘llanadi. Asl shablon o‘zgarmaydi. Word run formatlari va rasm tugunlari saqlanadi. Kirill matni kengroq bo‘lgani uchun 14 pt shriftni saqlagan holda qator balandligi 15.5 pt qilinadi va bo‘sh ajratgichlar qisqartiriladi. Rasm birinchi sahifada ekanligi PDF konversiyasida tekshiriladi.

**Tilmoch.ai holati:** sayt tekshirildi, tayyor ChatGPT plagini va foydalanishga ochiq, hujjatlashtirilgan transliteratsiya API shartnomasi topilmadi. Hozir Tilmoch.ai ulangan emas va unga foydalanuvchi ma’lumotlari yuborilmaydi. Yuqoridagi funksiyalar serverda mahalliy ishlaydi. Haqiqiy Tilmoch integratsiyasi uchun provayderning rasmiy API hujjatlari va tegishli xizmat ruxsati talab etiladi; noma’lum endpoint yoki taxminiy API so‘rovi ishlatilmagan.

## Tayyor bayonnoma ostida yozuvni almashtirish

Word va PDF yuborilgandan keyingi xabarda uchta inline tugma bor: **Kirillga o‘girish**, **Lotinga o‘girish**, **Yangi lotinga o‘girish**. Har tugma aynan o‘sha bayonnomaning asl kiritilgan maydonlari va tanlangan rasmidan yangi DOCX/PDF yaratadi. Ketma-ket qayta o‘girishdan xatolar yig‘ilmasligi uchun oldingi tayyor matn qayta transliteratsiya qilinmaydi; asl ma’lumotdan hujjat qayta yig‘iladi. Yangi fayl nomida `_Kirill`, `_Lotin` yoki `_Yangi_lotin` qo‘shimchasi bo‘ladi.

Yakunlangan bayonnomaning maydonlari va tanlangan PNG rasmi server RAM xotirasida tayyorlangandan boshlab **30 daqiqa** saqlanadi. Faol to‘ldirish sessiyasi yakunda tozalanadi, ammo ushbu alohida qayta tayyorlash keshi saqlanadi. Bir foydalanuvchining ko‘pi bilan oxirgi **5 ta** bayonnomasi saqlanadi; oltinchisi eng eskisini tozalaydi. Muddati tugagan ma’lumot 30 soniyalik tozalovchi tomonidan chiqariladi, tugma esa aniq muddat tugashi bilanoq ishlamaydi. Ishlayotgan qayta tayyorlash tugagach muddati o‘tgan kesh darhol tozalanadi. Bot restart/deploy qilinsa kesh ham yo‘qoladi.

**Saqlangan ma’lumotni o‘chirish** tugmasi shu bayonnomaning serverdagi maydonlari va rasmini olib tashlaydi. Telegram chatidagi allaqachon yuborilgan fayllarni o‘chirmaydi. Yangi bayonnoma boshlash avvalgi tugmalarni boshqa ma’lumotga yo‘naltirmaydi. Tugma ID larida F.I.Sh. yoki token yo‘q; egasi, shaxsiy chat va kirish cheklovlari har bosishda tekshiriladi. Bir foydalanuvchining parallel bosishlari navbatdagi hujjatni aralashtirmaydi.
