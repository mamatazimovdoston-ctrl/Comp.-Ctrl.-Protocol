"""Deterministic Uzbek script conversion. No translation or external requests.

Proper names and ambiguous Latin digraphs require the user's review.
"""
import re
import unicodedata

SCRIPTS={'latin':'Lotin yozuvi','cyrillic':'Kirill yozuvi','new_latin':'Yangi lotin yozuvi (ŏ, ğ, ş, ç)'}
APOSTROPHES="'‘’ʻʼ`´ʹˈ"
CYR={
'а':'a','б':'b','в':'v','г':'g','д':'d','ж':'j','з':'z','и':'i','й':'y',
'к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t',
'у':'u','ф':'f','х':'x','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ы':'i',
'э':'e','ю':'yu','я':'ya','ё':'yo','ў':'o‘','қ':'q','ғ':'g‘','ҳ':'h'}
LAT={'a':'а','b':'б','v':'в','g':'г','d':'д','j':'ж','z':'з','i':'и','y':'й',
'k':'к','l':'л','m':'м','n':'н','o':'о','p':'п','r':'р','s':'с','t':'т',
'u':'у','f':'ф','x':'х','q':'қ','h':'ҳ'}
GROUPS={'o‘':'ў','g‘':'ғ','sh':'ш','ch':'ч','yo':'ё','yu':'ю','ya':'я','ye':'е','ts':'ц'}

def normalize_apostrophes(text):
    text=unicodedata.normalize('NFC',text)
    text=text.translate(str.maketrans({'ŏ':'o‘','Ŏ':'O‘','ğ':'g‘','Ğ':'G‘','ş':'sh','Ş':'Sh','ç':'ch','Ç':'Ch'}))
    text=re.sub('['+re.escape(APOSTROPHES)+']','ʼ',text)
    # Fix keyboard hyphens only inside o-/g- letter combinations, never dates.
    text=re.sub(r'([oOgG])[-ʼ](?=[A-Za-zА-Яа-яЁёЎўҚқҒғҲҳ])',r'\1‘',text)
    text=re.sub(r'([oOgG])ʼ',r'\1‘',text)
    return text

def _cyr_word(word):
    upper=word.isupper() and len(word)>1;out=[]
    for i,c in enumerate(word):
        low=c.lower();prev=word[i-1].lower() if i else ''
        if low=='ь': value=''
        elif low=='ъ': value='' if i+1<len(word) and word[i+1].lower()=='е' else 'ʼ'
        elif low=='е':value='ye' if not prev or prev in 'аеёиоуўэюяъь' else 'e'
        else:value=CYR.get(low,c)
        if c.isupper():value=value.upper() if upper else value[:1].upper()+value[1:]
        out.append(value)
    return ''.join(out)

def to_latin(text):
    text=normalize_apostrophes(text)
    return re.sub(r'[А-Яа-яЁёЎўҚқҒғҲҳЪъЬь]+',lambda m:_cyr_word(m.group()),text)

def _lat_word(word):
    upper=word.isupper();out=[];i=0
    # Conventional loanword spellings need a separating hard sign.
    special={'obyekt':'объект','subyekt':'субъект','sudya':'судья'}
    months={'yanvar':'январь','fevral':'февраль','mart':'март','aprel':'апрель','may':'май','iyun':'июнь','iyul':'июль','avgust':'август','sentabr':'сентябрь','oktabr':'октябрь','noyabr':'ноябрь','dekabr':'декабрь'}
    if word.lower() in months:
        result=months[word.lower()]
        return result.upper() if upper else result.capitalize() if word[0].isupper() else result
    for stem,target in special.items():
        if word.lower().startswith(stem):
            result=target+_lat_word(word[len(stem):])
            return result.upper() if upper else result[:1].upper()+result[1:] if word[0].isupper() else result
    while i<len(word):
        c=word[i];pair=word[i:i+2].lower()
        if pair in GROUPS:value=GROUPS[pair];step=2
        elif c=='ʼ':value='ъ';step=1
        elif c=='‘':value='ъ';step=1
        elif c.lower()=='e':value='э' if i==0 else 'е';step=1
        else:value=LAT.get(c.lower(),c);step=1
        if c.isupper():value=value.upper()
        out.append(value);i+=step
    return ''.join(out)

def convert(text,script='latin'):
    if script not in SCRIPTS:raise ValueError('Yozuv turi noto‘g‘ri.')
    latin=to_latin(text)
    if script=='latin':return latin
    if script=='cyrillic':
        return re.sub(r'[A-Za-z‘ʼ]+',lambda m:_lat_word(m.group()),normalize_apostrophes(text))
    # Case-preserving digraph conversion; proper names remain recognizable.
    replacements={'o‘':'ŏ','O‘':'Ŏ','g‘':'ğ','G‘':'Ğ','sh':'ş','Sh':'Ş','SH':'Ş','ch':'ç','Ch':'Ç','CH':'Ç'}
    return re.sub(r'[oOgG]‘|[sS][hH]|[cC][hH]',lambda m:replacements.get(m.group(),replacements.get(m.group().lower(),m.group())),latin)
