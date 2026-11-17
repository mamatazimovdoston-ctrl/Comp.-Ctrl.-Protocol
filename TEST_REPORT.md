# Tekshiruv natijalari

2026-11-17. Python 3.12, LibreOffice Writer 25.2.3.2. Haqiqiy yuklangan shablondan foydalanildi.

**12 test o‘tdi**, jumladan 3 ta parametrli haqiqiy PDF konversiya testi. Tashqi anyio pytest plaginidan bitta deprecation warning bor; loyiha xatosi emas.

- Barcha 12 oy va noto‘g‘ri/kabisa sanalari tekshirildi.
- Word runlari orasiga bo‘lingan ismni almashtirish, qolgan run qalin/kursiv xususiyatlari saqlanishi tekshirildi.
- Huquqiy xatboshilar, ogohlantirish, sahifa sozlamalari va asl shablon SHA-256 qiymati saqlandi.
- Sarlavha, suhbat jumlasi, javobdagi qisqartma, ikki xodimning mustaqil imzo qismlari tekshirildi.
- Sana chapda, joy o‘ngda, chegarasiz jadvalning bitta qatorida. Uzun joyning davomi o‘ng katak ichida ikkinchi qatorga o‘tadi.
- Mavjud yagona DrawingML rasmi yangilandi; DOCX maydoni 6120000×3240000 EMU = 17×9 sm. PDF tasvir chegarasi ham shu o‘lchamda.
- Portret va keng tasvir markazda proporsiyasini saqlab neytral fonga joylandi, kesilmadi. Namuna rasmini qoldirishda original tasvir baytlari saqlandi.
- Olti parallel hujjat yaratuvchisida xodim ma’lumotlari aralashmadi.
- Telegram handlerlari uchun to‘liq kiritish, noto‘g‘ri sana, istalgan maydonni tahrirlash, bekor qilish, shaxsiy chat va kirish cheklovi testlari o‘tdi.
- Uchta DOCX/PDF juftligi yaratildi: Karimov (namuna rasmi), Rasulova (portret), Usmonov (uzun lavozim va joy, keng tasvir). Har biri 2 sahifa. Barchasida rasm birinchi sahifada.
- PDF sahifalari rastrga aylantirilib vizual ko‘rildi. Uzun matn uchun mavjud bo‘sh xatboshilar oralig‘i qisqartirildi. Natijada matn va imzolar kesilmasdan, rasm birinchi sahifaga sig‘di.

## Amaliy chegaralar

Token berilmagan: haqiqiy Telegram API bilan foto yuklash/hujjat yuborish sinovi va uzluksiz polling tekshirilmadi. Bot handlerlari test dublari bilan tekshirildi. Docker build/Railway deploy bajarilmadi; LibreOffice alohida mahalliy runtime orqali ishga tushirib sinovdan o‘tkazildi. Microsoft Word ilovasida mustaqil vizual taqqoslash bajarilmadi; DOCX tuzilmasi va undan LibreOffice chiqargan PDF tekshirildi. Docker Liberation Serif shriftidan foydalanishi mumkin.

Dastlab GitHub createRepository amali integratsiya ruxsati yetishmagani sababli rad etildi. Keyin foydalanuvchi Comp.-Ctrl.-Protocol repozitoriysini yaratdi va loyiha shu repozitoriyga joylash uchun tayyorlandi. Railway deploy hali bajarilmagan; BOT_TOKEN sozlanishi kerak.

## AI qirqish yangilanishi

Yuzlarni mahalliy o‘rgatilgan OpenCV detektorlari bilan aniqlash, barcha aniqlangan yuzlarni saqlaydigan 17:9 qirqish, yuz topilmaganda/model xatosida aslini sig‘dirish hamda Telegram preview tasdiqlash bosqichi qo‘shildi. Testlar qirqish geometriyasi, keng tarqalgan yuzlarda fallback, xatosiz model yuklanishi, oq tasvirda noto‘g‘ri yuz aniqlanmasligi, ikki variant orasida tanlash, rasmni almashtirish, bekor qilish va yuklangan surat tasdiqsiz qabul qilinmasligini qamraydi. Yuz/hujjatlarning to‘liq saqlanishi preview orqali foydalanuvchi tomonidan tekshiriladi; qo‘l yoki hujjat aniqlovchi alohida model ishlatilmaydi.

Yangilangan to‘liq test natijasi: **19 test o‘tdi** (haqiqiy LibreOffice PDF testlari bilan). OpenCV 4.12.0 detektori OpenCV rasm namunasida haqiqiy yuzni aniqladi. Foydalanuvchining shu chatdagi fotosida server qirqishi alohida sinovdan o‘tkazilmadi; bot preview orqali ko‘rib tasdiqlash mumkin.

## Uch yozuv va apostroflar yangilanishi

`transliteration.py` mahalliy o‘girish qoidalari qo‘shildi. Kirill, amaldagi lotin va ŏ/ğ/ş/ç varianti; o‘/g‘ va tutuq belgisini normalizatsiya qilish; ъ/ь qatnashadigan ayrim so‘zlar, oylar va sudya/obyekt/subyekt imlosi; tanlangan alifboga mos F.I.Sh. qisqartmalari tekshiriladi. Tasdiqlashdan oldin yozuvni o‘zgartirish va matnni qayta tekshirish mumkin.

9 ta haqiqiy LibreOffice sinovi: uchta yozuv × uchta sinov yozuvi. Har birida sana chapda, joy o‘ngda; rasm 17×9 sm va birinchi sahifada; har biri 2 sahifa. Uch yozuvda alohida DOCX/PDF namunalari `examples/Yozuv_*.docx/pdf` ichida. PDFlar rastrga aylantirilib vizual ko‘rildi; kirill uchun ixcham qator oralig‘i va rasmdan keyin sahifa uzilishi moslandi. Huquqiy matn mazmuni tarjima qilinmaydi — faqat yozuvi o‘giriladi.

Tilmoch.ai saytining ochiq sahifalari va plagin katalogi tekshirildi. Hujjatlashtirilgan ochiq transliteratsiya API shartnomasi yoki tayyor plagin topilmadi. Shu sababli tashqi Tilmoch API integratsiyasi bajarilmagan; uni ulangan deb ko‘rsatadigan xabar yo‘q. Barcha o‘girishlar lokal. Bu to‘liq lug‘atga ega imlo tekshirgich emas: foydalanuvchi ismlar va noodatiy so‘zlarni tasdiqlashi/tahrirlashi kerak.

To‘liq yangilangan natija: **37 test o‘tdi**, jumladan 9 ta haqiqiy PDF konversiya testi.
