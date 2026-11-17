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
