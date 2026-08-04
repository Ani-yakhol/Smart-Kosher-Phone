# פלאפון כשר חכם v1.0
## Smart Kosher Phone

דיבורית בלוטוס מתקדמת למחשב Windows

---

## הפעלה מהירה
```
run.bat
```

---

## קומפיל ל-EXE עצמאי (ללא Python)

### הכנה חד-פעמית
```
pip install nuitka zstandard ordered-set pyinstaller
pip install PySide6 bleak sounddevice vosk
```

---

### אפשרות א — קובץ EXE בודד (הכל כלול)
```
python -m nuitka ^
  --standalone ^
  --onefile ^
  --windows-console-mode=disable ^
  --windows-icon-from-ico=app\resources\icon.ico ^
  --output-filename=SmartKosherPhone.exe ^
  --output-dir=dist ^
  --include-package=app ^
  --include-package=bleak ^
  --include-package=vosk ^
  --include-data-dir=app\resources=app\resources ^
  --include-data-files=app\style_light.qss=app\style_light.qss ^
  --include-data-files=app\style_dark.qss=app\style_dark.qss ^
  --plugin-enable=pyside6 ^
  --windows-product-name="Smart Kosher Phone" ^
  --windows-product-version=1.0.0.0 ^
  main.py
```
**תוצאה:** `dist\SmartKosherPhone.exe` — קובץ אחד (~60-80MB), רץ בלי כלום

---

### אפשרות ב — תיקיית standalone (קובץ EXE קטן + קבצי משנה)
```
python -m nuitka ^
  --standalone ^
  --windows-console-mode=disable ^
  --windows-icon-from-ico=app\resources\icon.ico ^
  --output-filename=SmartKosherPhone.exe ^
  --output-dir=dist_dir ^
  --include-package=app ^
  --include-package=bleak ^
  --include-package=vosk ^
  --include-data-dir=app\resources=app\resources ^
  --include-data-files=app\style_light.qss=app\style_light.qss ^
  --include-data-files=app\style_dark.qss=app\style_dark.qss ^
  --plugin-enable=pyside6 ^
  main.py
```
**תוצאה:** `dist_dir\SmartKosherPhone.dist\` — תיקייה עם EXE קטן + DLLs. הפץ את כל התיקייה.

---

### PyInstaller (חלופה אם Nuitka נכשל)
```
:: קובץ אחד:
pyinstaller --onefile --windowed --name SmartKosherPhone ^
  --add-data "app\style_light.qss;app" ^
  --add-data "app\style_dark.qss;app" ^
  --add-data "app\resources;app\resources" ^
  --hidden-import bleak --hidden-import bleak.backends.winrt ^
  --hidden-import vosk --hidden-import sounddevice ^
  --hidden-import PySide6.QtMultimedia ^
  main.py

:: תיקיית standalone (EXE קטן):
pyinstaller --onedir --windowed --name SmartKosherPhone ^
  --add-data "app\style_light.qss;app" ^
  --add-data "app\style_dark.qss;app" ^
  --add-data "app\resources;app\resources" ^
  --hidden-import bleak --hidden-import vosk ^
  main.py
```

---

## v1.0 — מה חדש
- **מעבר לספריית PyQt6** — כל הממשק נבנה מחדש על גבי PyQt6 (במקום PySide6), כולל תיקון קפדני של כל ה-Enums שנדרשים ל-Qt6
- **עיצוב חדש לגמרי** — ערכות נושא בהיר/כהה מעוצבות מחדש: פינות מעוגלות, צבעוניות עקבית, מצבי hover/pressed/disabled ברורים לכל רכיב בתוכנה
- **אייקון מעוצב** — אייקון 256px חדש (פלאפון + סימון "כשר") משולב בסרגל הניווט, בלשונית אודות, ובקובץ ה-EXE
- **לשונית בית חכם מלאה** — שליטה ברכיבי בית חכם (כגון פיוז חכם) דרך קו טלפוני: הקצאת מקש לכל רכיב, מצבים מותאמים אישית, הכרזה קולית מוקלטת לכל רכיב, והפעלה/כיבוי לזמן קצוב עם כיבוי אוטומטי
- **אימות וחיזוק ארכיטקטורת הבלוטוס** — המחשב ממשיך להתחבר לפלאפון כדיבורית HFP לכל דבר (AT commands בלבד), עם בדיקה אמיתית שכל פקודה נשלחה בהצלחה לפני עדכון המצב בממשק
- **תרגום מלא לאנגלית** — כל טקסטי הממשק מתורגמים, כולל יישור LTR וסרגל ניווט שעובר לצד שמאל בשפה האנגלית (ונשאר מימין בעברית)
- **תמיכה במספר מכשירי בלוטוס** — רשימת מכשירים מוכרים עם שם מותאם אישית, סימון מכשיר ראשי, וזיהוי מספר הטלפון המחובר אוטומטית (AT+CNUM)
- **חיבור בלוטוס אמין יותר** — איתור ערוץ RFCOMM אמיתי דרך Windows (WinRT/SDP), חיבור-מחדש אוטומטי בניתוק לא צפוי, ותצוגת "מצב הדגמה" ברורה כשאין חיבור אמיתי
- **מתג הפעלה/כיבוי לכל לשונית** — ניתן לכבות זמנית שירות (למשל בית חכם) מבלי לאבד הגדרות
- **כפתור שליחה מודרני** בלשונית הודעות — חץ עגול שקוף
- שינוי שפה מיידי — RTL/LTR מוחל בלחיצה ללא הפעלה מחדש
- לשונית בייביסיטר — ניטור קולי מלא עם AI זיהוי בכי/קול
- `LanguageManager` מרכזי מנהל את כל שינויי השפה

## מבנה לשוניות
```
פלאפון כשר חכם v1.0
├── ממשק שיחה (חיוג / שיחה פעילה / אנשי קשר / יומן / הקלטות / הגדרות)
├── מכשירים (מכשירים מוכרים מרובים + סריקה + זיהוי מספר אוטומטי)
├── תא קולי (הודעות / כללי מענה / הודעות פתיח)
├── בייביסיטר (שלוחות / ניטור / התראות / מענה אוטומטי)
├── קו תכנים ← בפיתוח
├── הודעות (DTMF TextModem)
├── בית חכם ← חדש! (לוח בקרה / ניהול רכיבים / קו הבית החכם)
├── מחשב שלי ← בפיתוח
├── הגדרות (ססמה / שפה מיידית / ערכת נושא)
└── אודות
```

כל לשונית (מלבד מכשירים, הגדרות ואודות) כוללת מתג הפעלה/כיבוי בראשה.

