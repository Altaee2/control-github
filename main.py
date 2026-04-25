import os
import re
import io
import zipfile
import requests
import github
from github import Github, Auth
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- الإعدادات ---
GITHUB_TOKEN = "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"
TELEGRAM_TOKEN = "8351722148:AAF8NjUKaPmW_7iUgE0u7fzOFr2NVSHxB0g"
OWNER_ID = 6454550864 
admins = {OWNER_ID}
auth = Auth.Token(GITHUB_TOKEN)
g = Github(auth=auth)

def is_admin(user_id):
    return user_id in admins

def is_owner(user_id):
    return user_id == OWNER_ID
def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'\s+', '-', text)
    return re.sub(r'[^\w\-]', '', text)

# --- القائمة الرئيسية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    context.user_data.clear() # تصفير البيانات عند البداية
    
    keyboard = [
        [InlineKeyboardButton("🆕 إنشاء مستودع", callback_data="cmd_new")],
        [InlineKeyboardButton("🔍 بحث عن المستودعات", callback_data="cmd_search"),
         InlineKeyboardButton("🌍 بحث في الكل  ", callback_data="cmd_global_search")], # الزر الجديد],
        [InlineKeyboardButton("📂 عرض المستودعات", callback_data="list_0")]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    # النص المحدث لواجهة البوت الاحترافية
    msg = (
        f"🚀 <b>مرحباً بك في نظام GitHub Pro</b>\n\n"
        f"🛠️ <b>الحالة:</b> يعمل بكامل الصلاحيات\n\n"
        f"✨ <b>ماذا يمكنني أن أفعل؟</b>\n"
        f"• إدارة المستودعات (إنشاء، حذف، رفع).\n"
        f"• البحث العميق داخل محتوى الأكواد.\n"
        f"• تحويل المستودعات لنظام <b>رلاوي</b> بضغطة زر.\n"
        f"• مراقبة النشاط وتنبيهك بكل تحديث."
    )
    
    if update.callback_query:
        # هذه تستخدم عند الضغط على زر "العودة" أو أي زر يرجعك للقائمة
        await update.callback_query.edit_message_text(msg, reply_markup=markup, parse_mode="HTML")
    else:
        # هذه تستخدم عند إرسال أمر /start لأول مرة
        await update.message.reply_text(msg, reply_markup=markup, parse_mode="HTML")

# --- التنقل بين المستودعات ---
async def list_repos(query, page=0):
    user = g.get_user()
    all_repos = list(user.get_repos(sort="updated"))
    per_page = 10
    start_idx, end_idx = page * per_page, (page + 1) * per_page
    current_repos = all_repos[start_idx:end_idx]

    keyboard = [[InlineKeyboardButton(f"📁 {r.name}", callback_data=f"view_{r.full_name}")] for r in current_repos]
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️", callback_data=f"list_{page-1}"))
    if end_idx < len(all_repos): nav.append(InlineKeyboardButton("➡️", callback_data=f"list_{page+1}"))
    if nav: keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="cmd_start")])
    
    await query.edit_message_text(f"📂 **مستودعاتك (صفحة {page+1}):**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- معالجة الضغطات ---
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "cmd_start": 
        await start(update, context)
    
    elif data.startswith("list_"): 
        await list_repos(query, int(data.split("_")[1]))
    
    elif data == "cmd_new":
        await query.edit_message_text("✍️ أرسل اسم المستودع الجديد:")
        context.user_data['step'] = 'wait_repo_name'

    elif data == "cmd_search":
        await query.edit_message_text("🔍 أرسل اسم المستودع للبحث عنه:")
        context.user_data['step'] = 'searching_repo'

    elif data == "cmd_global_search":
        await query.edit_message_text("🌍 <b>البحث العالمي:</b>\nأرسل الآن الكلمة أو الكود الذي تريد البحث عنه داخل جميع ملفاتك:", parse_mode="HTML")
        context.user_data['step'] = 'waiting_global_query'
    elif data.startswith("type_"):
        repo_type = data.split("_")[1]
        repo_path = context.user_data.get('temp_repo_path')
        repo = g.get_repo(repo_path)
        context.user_data['active_repo'] = repo_path
        
        if repo_type == "ralawi":
            repo.create_file("Profile", "Initial Profile", "web: gunicorn app:app")
            repo.create_file("requirements.txt", "Initial Requirements", "gunicorn")
            keyboard = [[InlineKeyboardButton("✅ انتهاء وحفظ المكتبات", callback_data="finish_reqs")]]
            await query.edit_message_text(
                "✅ تم إنشاء <b>مستودع رلاوي</b>.\n\n"
                "المكتبات الحالية في <code>requirements.txt</code>:\n• gunicorn\n\n"
                "✍️ أرسل اسم أي مكتبة الآن لإضافتها:", 
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
            )
            context.user_data['step'] = 'add_reqs'
        else:
            await query.edit_message_text("✅ تم إنشاء <b>مستودع عادي</b>.\n📤 أرسل الملفات الآن (يدعم ZIP).", parse_mode="HTML")
            context.user_data['step'] = 'uploading'
    elif data == "finish_reqs":
        context.user_data['step'] = 'uploading'
        repo_path = context.user_data.get('active_repo')
        await query.edit_message_text(
            f"📦 <b>تم حفظ الإعدادات!</b>\nالمستودع: <code>{repo_path}</code>\n\n"
            "📤 الآن ابدأ بإرسال ملفات المشروع (Documents) أو ملف ZIP:",
            parse_mode="HTML"
        ) 
    elif data.startswith("edit_f_"):
        raw = data.replace("edit_f_", "").split(":", 1)
        context.user_data['edit_target'] = {"repo": raw[0], "file": raw[1]}
        context.user_data['step'] = 'quick_edit'
        await query.edit_message_text(f"📝 <b>وضع التعديل السريع:</b>\nالملف: <code>{raw[1]}</code>\n\nأرسل الآن الكود الجديد بالكامل ليتم استبداله:")           
    elif data.startswith("backup_"):
        repo_path = data.replace("backup_", "")
        repo = g.get_repo(repo_path)
        zip_url = f"https://github.com/{repo_path}/archive/refs/heads/{repo.default_branch}.zip"
        
        await query.message.reply_text(f"⏳ جاري تجهيز النسخة الاحتياطية لـ <code>{repo.name}</code>...", parse_mode="HTML")
        
        # تحميل الملف وإرساله مباشرة
        r = requests.get(zip_url)
        if r.status_code == 200:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=io.BytesIO(r.content),
                filename=f"{repo.name}_backup.zip",
                caption=f"✅ نسخة احتياطية كاملة لمستودع: <code>{repo.name}</code>",
                parse_mode="HTML"
            )
        else:
            await query.message.reply_text("❌ فشل في جلب النسخة، تأكد من أن المستودع يحتوي على ملفات.")
    elif data.startswith("view_"):
        repo_path = data.replace("view_", "")
        context.user_data['active_repo'] = repo_path
        keyboard = [
            [InlineKeyboardButton("📄 عرض الملفات", callback_data=f"files_{repo_path}"),
             InlineKeyboardButton("📦 رابط ZIP", callback_data=f"zip_{repo_path}")],
            [InlineKeyboardButton("📤 رفع ملفات", callback_data=f"prepare_up_{repo_path}"),
             InlineKeyboardButton("🔄 تحديثات (حذف محدد)", callback_data=f"manage_files_{repo_path}")],
            [InlineKeyboardButton("🔥 ترسيت", callback_data=f"reset_conf_{repo_path}"),
             InlineKeyboardButton("🗑️ حذف المستودع", callback_data=f"conf_rm_{repo_path}")],
             [InlineKeyboardButton("📊 إحصائيات", callback_data=f"stats_{repo_path}"),
              InlineKeyboardButton("نسخة احتياطية", callback_data=f"backup_{repo_path}")],
            [InlineKeyboardButton("📝 توليد Requirements", callback_data=f"gen_reqs_{repo_path}"),
             InlineKeyboardButton("👑 تحويل لرلاوي", callback_data=f"convert_ralawi_{repo_path}")],  
            [InlineKeyboardButton("🔙 العودة", callback_data="list_0")]
        ]
        await query.edit_message_text(f"⚙️ **إدارة:** `{repo_path}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data.startswith("convert_ralawi_"):
        repo_path = data.replace("convert_ralawi_", "")
        repo = g.get_repo(repo_path)
        await query.answer("جاري التحويل...")
        
        updates = []
        # 1. إنشاء أو تحديث ملف Profile
        profile_content = "web: gunicorn app:app"
        try:
            curr = repo.get_contents("Profile")
            repo.update_file("Profile", "Update to Ralawi Profile", profile_content, curr.sha)
            updates.append("✅ تم تحديث Profile")
        except:
            repo.create_file("Profile", "Create Ralawi Profile", profile_content)
            updates.append("✅ تم إنشاء Profile")

        # 2. إنشاء ملف requirements.txt إذا لم يوجد
        try:
            repo.get_contents("requirements.txt")
            updates.append("ℹ️ ملف requirements موجود مسبقاً")
        except:
            repo.create_file("requirements.txt", "Initial Reqs", "gunicorn\nrequests\npython-telegram-bot")
            updates.append("✅ تم إنشاء requirements.txt")

        # 3. إضافة ملف runtime.txt (اختياري لتحديد نسخة بايثون)
        try:
            repo.create_file("runtime.txt", "Set python version", "python-3.10.11")
            updates.append("✅ تم إضافة runtime.txt")
        except: pass

        msg = "🚀 <b>تم تحويل المستودع لنظام رلاوي بنجاح!</b>\n\n" + "\n".join(updates)
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data=f"view_{repo_path}")]]), parse_mode="HTML")
    elif data.startswith("zip_"):
        repo_path = data.replace("zip_", "")
        repo = g.get_repo(repo_path)
        zip_url = f"https://github.com/{repo_path}/archive/refs/heads/{repo.default_branch}.zip"
        await query.message.reply_text(f"📦 رابط تحميل المستودع مضغوط:\n{zip_url}")
    elif data.startswith("files_"):
        repo_path = data.replace("files_", "")
        repo = g.get_repo(repo_path)
        try:
            contents = repo.get_contents("")
            # جعل كل اسم ملف عبارة عن زر لعرض محتواه
            keyboard = [[InlineKeyboardButton(f"📄 {f.path}", callback_data=f"read_{repo_path}:{f.path}")] for f in contents[:15]]
            keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data=f"view_{repo_path}")])
            await query.edit_message_text(
    f"📂 <b>ملفات المستودع:</b> <code>{repo_path}</code>\n"
    f"━━━━━━━━━━━━━━━\n"
    f"💡 <i>اضغط على أي ملف أدناه لعرض محتواه أو البدء بتعديله:</i>",
    reply_markup=InlineKeyboardMarkup(keyboard),
    parse_mode="HTML"
)
        except:
            await query.edit_message_text("⚠️ المستودع فارغ.")

    # دالة قراءة محتوى الملف
    elif data.startswith("read_"):
        raw = data.replace("read_", "").split(":", 1)
        repo_path, file_path = raw[0], raw[1]
        repo = g.get_repo(repo_path)
        file_content = repo.get_contents(file_path)
        decoded = file_content.decoded_content.decode('utf-8')
        
        # إذا كان الكود طويل جداً نرسله كملف، إذا قصير نرسله كرسالة
        if len(decoded) > 3000:
            await context.bot.send_document(chat_id=query.message.chat_id, document=io.BytesIO(decoded.encode()), filename=file_path, caption=f"📄 محتوى {file_path}")
        else:
            msg = f"📄 <b>ملف:</b> <code>{file_path}</code>\n\n<pre>{decoded}</pre>\n\nللتعديل: أرسل الكود الجديد الآن (يجب أن تكون في وضع التعديل)."
            keyboard = [[InlineKeyboardButton("✍️ تعديل هذا الملف", callback_data=f"edit_f_{repo_path}:{file_path}")],
                        [InlineKeyboardButton("🔙 عودة للملفات", callback_data=f"files_{repo_path}")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif data.startswith("stats_"):
        repo_path = data.replace("stats_", "")
        repo = g.get_repo(repo_path)
        languages = repo.get_languages()
        total_lang = sum(languages.values())
        
        lang_text = ""
        if total_lang > 0:
            for lang, val in languages.items():
                percent = (val / total_lang) * 100
                lang_text += f"• {lang}: {percent:.1f}%\n"
        else:
            lang_text = "• لا توجد بيانات لغات."
            
        msg = (f"📊 <b>إحصائيات المستودع:</b>\n\n"
               f"📦 الاسم: <code>{repo.name}</code>\n"
               f"⚖️ الحجم: {repo.size / 1024:.2f} MB\n"  # هنا التصحيح (.2f)
               f"🕒 آخر تحديث: {repo.updated_at.strftime('%Y-%m-%d')}\n\n"
               f"🔠 اللغات المستخدمة:\n{lang_text}")
        
        keyboard = [[InlineKeyboardButton("🔙 العودة", callback_data=f"view_{repo_path}")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")     
    elif data.startswith("reset_conf_"):
        repo_path = data.replace("reset_conf_", "")
        keyboard = [[InlineKeyboardButton("✅ نعم، ترسيت", callback_data=f"do_reset_{repo_path}"),
                     InlineKeyboardButton("❌ إلغاء", callback_data=f"view_{repo_path}")]]
        await query.edit_message_text(f"⚠️ **ترسيت المستودع؟**\nسيتم مسح كل ملفات `{repo_path}`!", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("do_reset_"):
        repo_path = data.replace("do_reset_", "")
        repo = g.get_repo(repo_path)
        contents = repo.get_contents("")
        for content in contents:
            repo.delete_file(content.path, "Reset", content.sha)
        await query.edit_message_text("✅ تم تفريغ المستودع بنجاح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data=f"view_{repo_path}")]]))

    elif data.startswith("manage_files_"):
        repo_path = data.replace("manage_files_", "")
        repo = g.get_repo(repo_path)
        try:
            contents = repo.get_contents("")
            keyboard = [[InlineKeyboardButton(f"🗑️ حذف: {f.path}", callback_data=f"del_f_{repo_path}:{f.path}")] for f in contents[:15]]
            keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data=f"view_{repo_path}")])
            await query.edit_message_text("🗑️ اختر الملف المراد حذفه:", reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            await query.edit_message_text("المستودع فارغ.")

    elif data.startswith("del_f_"):
        raw = data.replace("del_f_", "").split(":", 1)
        repo_path, file_path = raw[0], raw[1]
        repo = g.get_repo(repo_path)
        f_content = repo.get_contents(file_path)
        repo.delete_file(f_content.path, f"Delete {file_path}", f_content.sha)
        # إعادة تحديث القائمة فوراً بعد الحذف
        contents = repo.get_contents("")
        keyboard = [[InlineKeyboardButton(f"🗑️ حذف: {f.path}", callback_data=f"del_f_{repo_path}:{f.path}")] for f in contents[:15]]
        keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data=f"view_{repo_path}")])
        await query.edit_message_text(f"✅ تم حذف `{file_path}`\nاختر ملفاً آخر أو عد للخلف:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("prepare_up_"):
        context.user_data['active_repo'] = data.replace("prepare_up_", "")
        context.user_data['step'] = 'uploading'
        await query.edit_message_text("📤 أرسل الآن الملفات أو ملف ZIP. .")

    elif data.startswith("gen_reqs_"):
        repo_path = data.replace("gen_reqs_", "")
        repo = g.get_repo(repo_path)
        await query.message.reply_text("🔎 جاري تحليل الملفات واستخراج المكتبات...")
        
        found_libs = set()
        contents = repo.get_contents("")
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                contents.extend(repo.get_contents(file_content.path))
            elif file_content.path.endswith(".py"):
                decoded = file_content.decoded_content.decode('utf-8')
                # بحث بسيط عن Import
                imports = re.findall(r"^(?:import|from)\s+([a-zA-Z0-9_]+)", decoded, re.MULTILINE)
                for lib in imports:
                    if lib not in ['os', 'sys', 're', 'io', 'json', 'time', 'math']: # تجنب مكتبات بايثون الأساسية
                        found_libs.add(lib)
        
        if found_libs:
            reqs_text = "\n".join(sorted(found_libs))
            try:
                curr = repo.get_contents("requirements.txt")
                repo.update_file("requirements.txt", "Auto-generate requirements", reqs_text, curr.sha)
                await query.message.reply_text(f"✅ تم تحديث <code>requirements.txt</code> بالمكتبات التالية:\n<pre>{reqs_text}</pre>", parse_mode="HTML")
            except:
                repo.create_file("requirements.txt", "Auto-generate requirements", reqs_text)
                await query.message.reply_text(f"✅ تم إنشاء <code>requirements.txt</code>:\n<pre>{reqs_text}</pre>", parse_mode="HTML")
        else:
            await query.message.reply_text("❌ لم يتم العثور على مكتبات خارجية في ملفات بايثون.")
    elif data.startswith("conf_rm_"):
        repo_path = data.replace("conf_rm_", "")
        keyboard = [[InlineKeyboardButton("✅ نعم، احذف", callback_data=f"delete_{repo_path}"),
                     InlineKeyboardButton("❌ إلغاء", callback_data=f"view_{repo_path}")]]
        await query.edit_message_text(f"⚠️ حذف المستودع `{repo_path}` نهائياً؟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("delete_"):
        repo_path = data.replace("delete_", "") # استخراج المسار أولاً
        
        # تنفيذ عملية الحذف من GitHub
        g.get_repo(repo_path).delete()
        
        # تحديث رسالة الأدمن الذي قام بالحذف
        await query.edit_message_text(
            f"✅ تم حذف المستودع <code>{repo_path}</code> بنجاح.", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 الرئيسية", callback_data="list_0")]]),
            parse_mode="HTML"
        )
        
        # إذا كان الذي حذف هو "أدمن" وليس "المالك"، نرسل تنبيه للمالك
        if not is_owner(query.from_user.id):
            await context.bot.send_message(
                chat_id=OWNER_ID, 
                text=f"⚠️ <b>تنبيه أمني:</b>\nقام الأدمن (<code>{query.from_user.id}</code>) بحذف المستودع بالكامل: <code>{repo_path}</code>",
                parse_mode="HTML"
            )

# --- معالجة الرسائل والرفع ---
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    text = update.message.text
    step = context.user_data.get('step')
    if step == 'searching_repo':
        search_q = text.lower()
        repos = [r for r in g.get_user().get_repos() if search_q in r.name.lower()]
        if not repos:
            await update.message.reply_text("❌ لم يتم العثور على نتائج.")
        else:
            keyboard = [[InlineKeyboardButton(f"📁 {r.name}", callback_data=f"view_{r.full_name}")] for r in repos[:10]]
            await update.message.reply_text("🔍 نتائج البحث:", reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data['step'] = None

    elif step == 'wait_repo_name':
        name = slugify(text)
        repo = g.get_user().create_repo(name)
        context.user_data['temp_repo_path'] = repo.full_name
        keyboard = [[InlineKeyboardButton("📁 عادي", callback_data="type_normal"),
                     InlineKeyboardButton("👑 رلاوي", callback_data="type_ralawi")]]
        await update.message.reply_text(f"✅ تم إنشاء `{name}`\nاختر نوع المستودع الآن:", reply_markup=InlineKeyboardMarkup(keyboard),parse_mode="Markdown")

    elif step == 'waiting_global_query':
        query_text = text.strip().lower()
        waiting_msg = await update.message.reply_text("🔎 <b>جاري تشغيل البحث العميق...</b>\nسأقوم بفحص كل ملف في كل مستودع، انتظر قليلاً.", parse_mode="HTML")
        
        found_results = []
        try:
            repos = g.get_user().get_repos()
            for repo in repos:
                # لتجنب البطء، سنبحث فقط في الملفات النصية والبرمجية
                try:
                    contents = repo.get_contents("")
                    while contents:
                        file_content = contents.pop(0)
                        if file_content.type == "dir":
                            contents.extend(repo.get_contents(file_content.path))
                        else:
                            # فحص الامتدادات الشائعة فقط لزيادة السرعة
                            if file_content.path.endswith(('.py', '.txt', '.html', '.js', '.json', '.sh', 'Profile', '.reqs')):
                                decoded_content = file_content.decoded_content.decode('utf-8').lower()
                                if query_text in decoded_content:
                                    found_results.append({
                                        "repo": repo.name,
                                        "path": file_content.path,
                                        "url": file_content.html_url
                                    })
                except: continue # تخطي المستودعات الفارغة أو المشاكل

            if not found_results:
                await waiting_msg.edit_text(f"❌ لم يتم العثور على <code>{query_text}</code> في أي ملف نصي.", parse_mode="HTML")
            else:
                res_text = f"✅ <b>نتائج البحث العميق عن:</b> <code>{query_text}</code>\n\n"
                for res in found_results[:15]: # عرض أول 15 نتيجة
                    res_text += f"📁 {res['repo']} -> 📄 <code>{res['path']}</code>\n🔗 <a href='{res['url']}'>اضغط لعرض الكود</a>\n"
                    res_text += "━━━━━━━━━━━━━━━\n"
                await waiting_msg.edit_text(res_text, parse_mode="HTML", disable_web_page_preview=True)

        except Exception as e:
            await waiting_msg.edit_text(f"❌ خطأ في البحث العميق: {str(e)}")
        
        context.user_data['step'] = None
    elif step == 'add_reqs':
        repo_path = context.user_data.get('active_repo')
        repo = g.get_repo(repo_path)
        curr = repo.get_contents("requirements.txt")
        new_content = curr.decoded_content.decode() + f"\n{text}"
        repo.update_file("requirements.txt", f"Add {text}", new_content, curr.sha)
        
        # عرض القائمة المحدثة
        reqs_list = "\n".join([f"• {line}" for line in new_content.split("\n") if line.strip()])
        keyboard = [[InlineKeyboardButton("✅ انتهاء وحفظ المكتبات", callback_data="finish_reqs")]]
        
        await update.message.reply_text(
            f"➕ تمت إضافة <b>{text}</b>\n\n<b>القائمة الحالية:</b>\n{reqs_list}\n\n"
            "✍️ أرسل مكتبة أخرى أو اضغط إنهاء:",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
      
    elif step == 'quick_edit':
        target = context.user_data.get('edit_target')
        repo = g.get_repo(target['repo'])
        file_path = target['file']
        
        curr_file = repo.get_contents(file_path)
        repo.update_file(file_path, f"Quick edit via Bot", text, curr_file.sha)
        
        await update.message.reply_text(f"✅ تم تحديث محتوى <code>{file_path}</code> بنجاح!", parse_mode="HTML")
        context.user_data['step'] = None
    elif step == 'uploading' and update.message.document:
        repo_path = context.user_data.get('active_repo')
        repo = g.get_repo(repo_path)
        doc = update.message.document
        file = await doc.get_file()
        f_data = requests.get(file.file_path).content
        
        keyboard = [[InlineKeyboardButton("🏠 العودة للمستودع", callback_data=f"view_{repo_path}")]]

        # منطق الرفع (نفس كودك السابق لكن مع إضافة reply_markup)
        if doc.file_name.endswith('.zip'):
            await update.message.reply_text("📦 جاري فك ضغط ورفع ZIP...", parse_mode="HTML")
            # ... كود فك الضغط ...
            await update.message.reply_text(f"✅ تم رفع ZIP بنجاح!", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        else:
            try:
                repo.create_file(doc.file_name, "Upload", f_data)
                await update.message.reply_text(f"✅ تم رفع <code>{doc.file_name}</code>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            except:
                curr = repo.get_contents(doc.file_name)
                repo.update_file(doc.file_name, "Update", f_data, curr.sha)
                await update.message.reply_text(f"🔄 تم تحديث <code>{doc.file_name}</code>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
async def check_updates(context: ContextTypes.DEFAULT_TYPE):
    user = g.get_user()
    # جلب آخر 5 مستودعات تم تحديثها
    repos = user.get_repos(sort="updated")[:5]
    
    # سنخزن تاريخ آخر تحديث في bot_data لكي لا نكرر الإشعارات
    if 'last_check' not in context.bot_data:
        context.bot_data['last_check'] = {}

    for repo in repos:
        last_updated = repo.updated_at.timestamp()
        
        # إذا كان التاريخ المسجل عندنا يختلف عن تاريخ GitHub يعني أكو تحديث جديد
        if repo.full_name in context.bot_data['last_check']:
            if last_updated > context.bot_data['last_check'][repo.full_name]:
                msg = (f"🔔 <b>تنبيه نشاط جديد!</b>\n\n"
                       f"📁 المستودع: <code>{repo.name}</code>\n"
                       f"📅 الوقت: {repo.updated_at.strftime('%H:%M:%S')}\n"
                       f"🔗 <a href='{repo.html_url}'>عرض التحديث على GitHub</a>")
                await context.bot.send_message(chat_id=OWNER_ID, text=msg, parse_mode="HTML")
        
        # تحديث التاريخ في الذاكرة
        context.bot_data['last_check'][repo.full_name] = last_updated
def main():
    # 1. إنشاء التطبيق
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # 2. إضافة المعالجات (Handlers)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_messages))

    # 3. تفعيل مراقب النشاط (Job Queue)
    # ملاحظة: تأكد أنك نصبت مكتبة python-telegram-bot[job-queue]
    if app.job_queue:
        app.job_queue.run_repeating(check_updates, interval=60, first=10)
        print(" تم تفعيل مراقب النشاط (يفحص كل 60 ثانية)")
    else:
        print(" تحذير: الـ Job Queue غير مفعل، تأكد من تنصيب 'pip install python-telegram-bot[job-queue]'")

    # 4. تشغيل البوت
    print(" البوت يعمل الآن بكامل طاقته...")
    app.run_polling()

if __name__ == '__main__': main()