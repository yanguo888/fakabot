#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import json
import re
import os
import sqlite3
import time
import socket

import requests
from flask import Flask, request
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes
import logging
from waitress import serve
import hashlib
from admin_panel import register_admin_handlers
from user_flow import register_user_handlers
from utils import ensure_settings_table, get_setting, set_setting

# Redis缓存和频率限制
try:
    from redis_cache import cache
    from rate_limiter import check_ip_rate_limit
    REDIS_ENABLED = True
    print("✅ Redis缓存和频率限制已启用")
except ImportError as e:
    print(f"⚠️ Redis模块未安装，缓存功能已禁用: {e}")
    REDIS_ENABLED = False
    def check_ip_rate_limit(ip, rule):
        return True, None

app = Flask(__name__)

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
CFG_PATH = os.path.join(BASE_DIR, "config.json")
os.makedirs(DATA_DIR, exist_ok=True)

if not os.path.exists(CFG_PATH):
    raise SystemExit(
        "未找到 config.json，请先根据 config.json.example 创建并填写你的配置后再运行。"
    )

LAST_MSG_ID = {}

def _db_get_last_msg_id(chat_id: int):
    try:
        row = cur.execute("SELECT message_id FROM last_msgs WHERE chat_id=?", (int(chat_id),)).fetchone()
        return row[0] if row else None
    except Exception:
        return None

def _db_set_last_msg_id(chat_id: int, message_id: int):
    try:
        cur.execute(
            "INSERT INTO last_msgs(chat_id, message_id) VALUES(?, ?) ON CONFLICT(chat_id) DO UPDATE SET message_id=excluded.message_id",
            (int(chat_id), int(message_id)),
        )
        conn.commit()
    except Exception:
        pass

async def _delete_last_and_send_text(chat_id: int, text: str, reply_markup=None, disable_web_page_preview: bool = False, parse_mode=None):
    mid = LAST_MSG_ID.get(chat_id)
    if not mid:
        mid = _db_get_last_msg_id(chat_id)
        if mid:
            LAST_MSG_ID[chat_id] = mid
    if mid:
        try:
            await application.bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass
    m = await application.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        disable_web_page_preview=disable_web_page_preview,
        parse_mode=parse_mode,
    )
    LAST_MSG_ID[chat_id] = m.message_id
    _db_set_last_msg_id(chat_id, m.message_id)
    return m

def _ensure_settings_table():
    # 使用通用实现；此函数保留名称以兼容后续调用位置
    try:
        ensure_settings_table(cur, conn)
    except Exception:
        pass

def _get_setting(key: str, default: str = "") -> str:
    try:
        return get_setting(cur, key, default)
    except Exception:
        return default

def _set_setting(key: str, value: str):
    try:
        set_setting(cur, conn, key, value)
    except Exception:
        pass

def _bootstrap_home_from_cfg_if_empty():
    title = _get_setting("home.title", "")
    intro = _get_setting("home.intro", "")
    cover = _get_setting("home.cover_url", "")
    if not (title or intro or cover):
        try:
            _set_setting("home.title", (START_CFG.get("title") or "欢迎选购"))
            _set_setting("home.intro", (START_CFG.get("intro") or "请选择下方商品进行购买"))
            if START_CFG.get("cover_url"):
                _set_setting("home.cover_url", START_CFG.get("cover_url"))
        except Exception:
            pass

 

async def _delete_last_and_send_photo(chat_id: int, photo, caption: str = None, reply_markup=None, parse_mode=None):
    mid = LAST_MSG_ID.get(chat_id)
    if not mid:
        mid = _db_get_last_msg_id(chat_id)
        if mid:
            LAST_MSG_ID[chat_id] = mid
    if mid:
        try:
            await application.bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass
    m = await application.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
    LAST_MSG_ID[chat_id] = m.message_id
    _db_set_last_msg_id(chat_id, m.message_id)
    return m

def _strip_json_comments(s: str) -> str:
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    out_lines = []
    in_str = False
    esc = False
    for line in s.splitlines():
        buf = []
        in_str = False
        esc = False
        for i, ch in enumerate(line):
            if ch == '"' and not esc:
                in_str = not in_str
            if not in_str and i+1 < len(line) and ch == '/' and line[i+1] == '/':
                break
            buf.append(ch)
            esc = (ch == '\\' and not esc)
            if ch != '\\':
                esc = False
        out_lines.append("".join(buf).rstrip())
    return "\n".join(out_lines)

with open(CFG_PATH, "r", encoding="utf-8") as f:
    _raw = f.read()
    CFG = json.loads(_strip_json_comments(_raw))

BOT_TOKEN = CFG["BOT_TOKEN"]
ADMIN_ID = int(CFG["ADMIN_ID"])
DOMAIN = CFG.get("DOMAIN", "http://127.0.0.1")
USE_WEBHOOK = bool(CFG.get("USE_WEBHOOK", False))
WEBHOOK_PATH = CFG.get("WEBHOOK_PATH", "/tg/webhook")
WEBHOOK_SECRET = CFG.get("WEBHOOK_SECRET") or hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:32]
ORDER_TIMEOUT_SECONDS = int(CFG.get("ORDER_TIMEOUT_SECONDS", 900))
PAYCFG = CFG["PAYMENTS"]
PRODUCTS_CFG = CFG.get("PRODUCTS", [])
START_CFG = CFG.get("START", {})  # {"cover_url": str, "intro": str, "title": str}
SHOW_QR = bool(CFG.get("SHOW_QR", True))
STRICT_CALLBACK_SIGN_VERIFY = bool(CFG.get("STRICT_CALLBACK_SIGN_VERIFY", True))
ENABLE_PAYMENT_SCREENSHOT = bool(CFG.get("ENABLE_PAYMENT_SCREENSHOT", True))
# ✅ 修复：从PAYMENTS中读取TOKEN188配置
TOKEN188_CFG = PAYCFG.get("usdt_token188", {})

def _detect_client_ip():
    override = CFG.get("CLIENT_IP")
    if override:
        return override
    try:
        ip = requests.get("https://api.ipify.org", timeout=5).text.strip()
        if ip:
            return ip
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

CLIENT_IP = _detect_client_ip()

 
DB_PATH = os.path.join(DATA_DIR, "sp_shop.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()

try:
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA busy_timeout=5000;")
    conn.commit()
except Exception:
    pass

_ensure_settings_table()
_bootstrap_home_from_cfg_if_empty()

cur.execute(
    """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cover_url TEXT,
    description TEXT,
    full_description TEXT,
    image_url TEXT,
    price REAL NOT NULL,
    tg_group_id TEXT NOT NULL,
    deliver_type TEXT NOT NULL DEFAULT 'join_group'
)
"""
)
try:
    cur.execute("ALTER TABLE products ADD COLUMN status TEXT NOT NULL DEFAULT 'on'")
    conn.commit()
except Exception:
    pass
try:
    cur.execute("ALTER TABLE products ADD COLUMN sort INTEGER")
    conn.commit()
except Exception:
    pass
try:
    # 回填初始排序：若为空则以 id 作为默认排序值（越大越靠前）
    cur.execute("UPDATE products SET sort = id WHERE sort IS NULL")
    conn.commit()
except Exception:
    pass
try:
    cur.execute("UPDATE products SET status='on' WHERE status IS NULL")
    conn.commit()
except Exception:
    pass

cur.execute(
    """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    payment_method TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    out_trade_no TEXT NOT NULL UNIQUE,
    create_time INTEGER NOT NULL
)
"""
)
cur.execute(
    """
CREATE TABLE IF NOT EXISTS last_msgs (
    chat_id INTEGER PRIMARY KEY,
    message_id INTEGER NOT NULL
)
"""
)
conn.commit()

cur.execute(
    """
CREATE TABLE IF NOT EXISTS invites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    group_id TEXT NOT NULL,
    invite_link TEXT NOT NULL,
    create_time INTEGER NOT NULL,
    expire_time INTEGER NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0
)
"""
)
conn.commit()

# Create useful indexes for performance
try:
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_out_trade_no ON orders(out_trade_no)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_status_user ON orders(status, user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_invites_link ON invites(invite_link)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_invites_user_group ON invites(user_id, group_id, revoked, expire_time)")
    conn.commit()
except Exception:
    pass

# --- Migrations for card delivery ---
try:
    cur.execute("ALTER TABLE products ADD COLUMN card_fixed TEXT")
    conn.commit()
except Exception:
    pass
try:
    cur.execute(
        """
CREATE TABLE IF NOT EXISTS card_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    key_text TEXT NOT NULL,
    used_by_order_id INTEGER,
    used_time INTEGER,
    create_time INTEGER NOT NULL
)
"""
    )
    conn.commit()
except Exception:
    pass
try:
    cur.execute("CREATE INDEX IF NOT EXISTS idx_card_keys_prod_used ON card_keys(product_id, used_by_order_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_card_keys_prod_id ON card_keys(product_id, id)")
    conn.commit()
except Exception:
    pass

# --- TOKEN188 USDT交易记录表 ---
try:
    cur.execute(
        """
CREATE TABLE IF NOT EXISTS usdt_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    out_trade_no TEXT NOT NULL,
    transaction_id TEXT NOT NULL UNIQUE,
    from_address TEXT NOT NULL,
    amount REAL NOT NULL,
    create_time INTEGER NOT NULL
)
"""
    )
    conn.commit()
except Exception:
    pass
try:
    cur.execute("CREATE INDEX IF NOT EXISTS idx_usdt_trans_order ON usdt_transactions(out_trade_no)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_usdt_trans_txid ON usdt_transactions(transaction_id)")
    conn.commit()
except Exception:
    pass

def _mark_paid_and_deliver(out_trade_no: str, conn_override=None, cur_override=None):
    _conn = conn_override or conn
    _cur = cur_override or cur
    row = _cur.execute(
        "SELECT id, user_id, product_id, status FROM orders WHERE out_trade_no=?",
        (out_trade_no,),
    ).fetchone()
    if not row:
        return
    oid, uid, pid, status = row
    reissue = False
    if status != "pending":
        if status == "paid":
            # 仅当不存在“仍然有效的邀请”时才重发：revoked=0 且未过期
            now_ts = int(time.time())
            exist_active = _cur.execute(
                "SELECT 1 FROM invites WHERE order_id=? AND revoked=0 AND expire_time>? LIMIT 1",
                (oid, now_ts),
            ).fetchone()
            if not exist_active:
                reissue = True
            else:
                # 已有有效邀请则不再重复发
                return
        else:
            return

    if not reissue:
        _cur.execute("UPDATE orders SET status='paid' WHERE id=?", (oid,))
        _conn.commit()

    prod_row = _cur.execute("SELECT tg_group_id, name, deliver_type, card_fixed FROM products WHERE id=?", (pid,)).fetchone()
    if not prod_row:
        # 通常是商品被删除或尚未创建，避免静默失败：通知管理员并提醒用户
        async def _notify_missing():
            try:
                await application.bot.send_message(
                    ADMIN_ID,
                    text=f"[告警] 订单 {out_trade_no} 所属商品(id={pid})不存在，无法生成邀请链接。已将订单置为已支付。"
                )
            except Exception:
                pass
            try:
                await application.bot.send_message(
                    uid,
                    text="支付成功，但商品配置暂时缺失，管理员将尽快处理，请稍候。"
                )
            except Exception:
                pass
        try:
            try:
                # 优先在当前事件循环中异步调度
                loop = asyncio.get_running_loop()
                loop.create_task(_notify_missing())
            except RuntimeError:
                # 若当前无运行中的事件循环（例如独立线程/进程），则直接运行
                asyncio.run(_notify_missing())
        except Exception:
            pass
        return
    group_id, name, deliver_type, card_fixed = prod_row

    # Branch by deliver_type
    dt = (deliver_type or 'join_group').strip().lower()
    if dt == 'card_fixed' or dt == 'card_pool':
        async def _send_text(to_uid: int, text: str):
            try:
                await application.bot.send_message(to_uid, text=text)
            except Exception:
                try:
                    await application.bot.send_message(
                        ADMIN_ID,
                        text=f"[告警] 无法给用户 {to_uid} 发送消息，请确认用户已与机器人开始对话。"
                    )
                except Exception:
                    pass

        async def deliver_card():
            try:
                # Determine card content
                card_text = None
                if dt == 'card_fixed':
                    card_text = (card_fixed or '').strip()
                    if not card_text:
                        await _send_text(uid, f"支付成功：{name}\n管理员尚未配置通用卡密，请稍后。")
                        try:
                            await application.bot.send_message(ADMIN_ID, f"[缺货/未配置] 订单 {out_trade_no} 商品({pid}) 为通用卡密发货，但未配置 card_fixed。")
                        except Exception:
                            pass
                        return
                else:
                    # card_pool: pick first unused with optimistic concurrency (retry)
                    max_try = 5
                    success = False
                    card_text = None
                    for _ in range(max_try):
                        row_key = _cur.execute(
                            "SELECT id, key_text FROM card_keys WHERE product_id=? AND used_by_order_id IS NULL ORDER BY id ASC LIMIT 1",
                            (pid,)
                        ).fetchone()
                        if not row_key:
                            break
                        key_id, card_text = row_key
                        now_ts = int(time.time())
                        try:
                            _cur.execute(
                                "UPDATE card_keys SET used_by_order_id=?, used_time=? WHERE id=? AND used_by_order_id IS NULL",
                                (oid, now_ts, key_id),
                            )
                            if _cur.rowcount == 1:
                                _conn.commit()
                                success = True
                                break
                            else:
                                # 被并发抢占，重试
                                _conn.rollback()
                                await asyncio.sleep(0.05)
                        except Exception:
                            try:
                                _conn.rollback()
                            except Exception:
                                pass
                            await asyncio.sleep(0.05)
                    if not success or not card_text:
                        await _send_text(uid, f"支付成功：{name}\n但当前卡密库存不足，已通知管理员补充，请稍候。")
                        try:
                            await application.bot.send_message(ADMIN_ID, f"[缺货] 订单 {out_trade_no} 商品({pid}) 无可用卡密。")
                        except Exception:
                            pass
                        return

                # Send card to user
                msg = (
                    f"✅ 支付成功：{name}\n"
                    f"🔐 您的卡密：\n{card_text}\n\n"
                    f"请妥善保管。"
                )
                try:
                    await _send_text(uid, msg)
                except Exception:
                    pass

                # Mark order as completed
                try:
                    _cur.execute("UPDATE orders SET status='completed' WHERE id=?", (oid,))
                    _conn.commit()
                except Exception:
                    pass
                # Notify admin
                try:
                    await application.bot.send_message(ADMIN_ID, f"[成交通知-卡密]\n商品：{name}\n用户：{uid}\n订单：{out_trade_no}")
                except Exception:
                    pass
            except Exception as e:
                try:
                    await application.bot.send_message(ADMIN_ID, f"[错误] 发卡失败：订单 {out_trade_no} err={e}")
                except Exception:
                    pass

        try:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(deliver_card())
            except RuntimeError:
                asyncio.run(deliver_card())
        except Exception:
            pass
        return

    async def _send_text(to_uid: int, text: str):
        try:
            await application.bot.send_message(to_uid, text=text)
        except Exception as e:
            # 发送到用户失败时，通知管理员以便排障（常见原因：用户未与机器人发起私聊、被拉黑、用户ID错误）
            try:
                await application.bot.send_message(
                    ADMIN_ID,
                    text=f"[告警] 无法给用户 {to_uid} 发送消息：{e}\n可能原因：1) 用户未与机器人开始对话 2) 用户拉黑/限制 3) 用户ID不正确"
                )
            except Exception:
                pass

    async def create_invite_and_notify():
        try:
            expire_at = int(time.time()) + 3600
            last_err = None
            for attempt in range(3):
                try:
                    link_obj = await application.bot.create_chat_invite_link(
                        chat_id=group_id,
                        expire_date=expire_at,
                        member_limit=1,
                    )
                    break
                except Exception as e:
                    last_err = e
                    if attempt < 2:
                        await asyncio.sleep(0.5 * (2 ** attempt))
                    else:
                        raise
            invite_link = link_obj.invite_link
            _cur.execute(
                "INSERT INTO invites (order_id, user_id, group_id, invite_link, create_time, expire_time, revoked) VALUES (?,?,?,?,?,?,0)",
                (oid, uid, str(group_id), invite_link, int(time.time()), expire_at),
            )
            _conn.commit()
            msg = (
                f"✅ 支付成功：{name}\n"
                f"这是您的自动拉群邀请链接（1小时内有效，且仅可使用一次）：\n\n{invite_link}\n\n"
                f"请尽快点击加入群组。加入成功后我会自动撤销该链接。"
            )
            try:
                await _delete_last_and_send_text(uid, msg)
            except Exception:
                pass
        except Exception as e:
            try:
                await application.bot.send_message(
                    ADMIN_ID,
                    text=f"[错误] 为订单 {out_trade_no} 生成邀请链接失败：{e}"
                )
            except Exception:
                pass
            await _send_text(uid, f"支付成功：{name}\n系统生成邀请链接失败，请稍后重试或等待管理员手工处理。")

    try:
        try:
            # 在当前运行中的事件循环中调度发送任务
            loop = asyncio.get_running_loop()
            loop.create_task(create_invite_and_notify())
        except RuntimeError:
            # 若当前上下文无事件循环，则直接运行
            asyncio.run(create_invite_and_notify())
    except Exception:
        pass


# -----------------------------
# Telegram Bot
# -----------------------------
application = Application.builder().token(BOT_TOKEN).build()

try:
    register_admin_handlers(
        application,
        {
            "is_admin": is_admin if 'is_admin' in globals() else (lambda uid: uid == ADMIN_ID),
            "cur": cur,
            "conn": conn,
            "CFG_PATH": CFG_PATH,
            "START_CFG": START_CFG,
            "_delete_last_and_send_text": _delete_last_and_send_text,
            "_delete_last_and_send_photo": _delete_last_and_send_photo,
            "mark_paid_and_send_invite": _mark_paid_and_deliver,
            "_get_setting": _get_setting,
            "_set_setting": _set_setting,
        },
    )
except Exception:
    pass

try:
    register_user_handlers(
        application,
        {
            "cur": cur,
            "conn": conn,
            "PAYCFG": PAYCFG,
            "START_CFG": START_CFG,
            "SHOW_QR": SHOW_QR,
            "ENABLE_PAYMENT_SCREENSHOT": ENABLE_PAYMENT_SCREENSHOT,
            "ORDER_TIMEOUT_SECONDS": ORDER_TIMEOUT_SECONDS,
            "ADMIN_ID": ADMIN_ID,
            "DOMAIN": DOMAIN,
            "CLIENT_IP": CLIENT_IP,
            "TOKEN188_CFG": TOKEN188_CFG,
            "_delete_last_and_send_text": _delete_last_and_send_text,
            "_delete_last_and_send_photo": _delete_last_and_send_photo,
            "_get_setting": _get_setting,
            "mark_paid_and_deliver": _mark_paid_and_deliver,
        },
    )
except Exception:
    pass

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def _verify_callback_signature(params: dict, payment_configs: dict) -> bool:
    """
    验证支付回调签名 - 使用新的支付模块
    
    Args:
        params: 回调参数
        payment_configs: 支付配置字典
        
    Returns:
        bool: 签名验证结果
    """
    try:
        from payments import verify_callback_signature
        
        # 遍历所有支付通道进行验证
        for ch_name, ch_config in (payment_configs or {}).items():
            if not isinstance(ch_config, dict):
                continue
            
            try:
                if verify_callback_signature(ch_config, params):
                    print(f"✅ 回调签名验证成功: {ch_name}")
                    return True
            except Exception as e:
                print(f"⚠️ 通道 {ch_name} 签名验证失败: {e}")
                continue
        
        print("❌ 所有支付通道签名验证都失败")
        return False
        
    except Exception as e:
        print(f"❌ 回调签名验证异常: {e}")
        return False


# 向后兼容的函数别名
def md5_sign(params: dict, key: str) -> str:
    """向后兼容的MD5签名函数"""
    from payments import md5_sign as payments_md5_sign
    return payments_md5_sign(params, key)


def _verify_md5_sign(params: dict, key: str) -> bool:
    """向后兼容的签名验证函数"""
    if not key:
        return False
    recv = (params.get("sign") or "").lower()
    if not recv:
        return False
    calc = md5_sign(params, key)
    return recv == calc


async def job_cancel_expired(ctx: ContextTypes.DEFAULT_TYPE):
    def get_payment_timeout_seconds(channel: str) -> int:
        """根据支付方式返回不同的订单超时时间"""
        timeout_config = {
            "usdt_token188": 60 * 60,      # TOKEN188支付：60分钟
            "usdt_lemon": 120 * 60,        # 柠檬USDT：120分钟
            "alipay": 10 * 60,             # 支付宝：10分钟
            "wxpay": 10 * 60,              # 微信支付：10分钟
        }
        return timeout_config.get(channel, ORDER_TIMEOUT_SECONDS)  # 默认使用配置文件中的值
    
    now = int(time.time())
    rows = cur.execute(
        "SELECT id, user_id, out_trade_no, create_time, payment_method FROM orders WHERE status='pending'"
    ).fetchall()
    for oid, uid, out_trade_no, create_time, payment_method in rows:
        timeout_seconds = get_payment_timeout_seconds(payment_method)
        if now - create_time > timeout_seconds:
            cur.execute("UPDATE orders SET status='cancelled' WHERE id=?", (oid,))
            conn.commit()


async def cmd_reloadcfg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            _raw = f.read()
            cfg_new = json.loads(_strip_json_comments(_raw))
        global CFG, BOT_TOKEN, ADMIN_ID, DOMAIN, ORDER_TIMEOUT_SECONDS, PAYCFG, PRODUCTS_CFG, START_CFG, SHOW_QR, STRICT_CALLBACK_SIGN_VERIFY, ENABLE_PAYMENT_SCREENSHOT, TOKEN188_CFG
        CFG = cfg_new
        BOT_TOKEN = CFG["BOT_TOKEN"]
        ADMIN_ID = int(CFG["ADMIN_ID"])
        DOMAIN = CFG.get("DOMAIN", "http://127.0.0.1")
        ORDER_TIMEOUT_SECONDS = int(CFG.get("ORDER_TIMEOUT_SECONDS", 900))
        PAYCFG = CFG["PAYMENTS"]
        PRODUCTS_CFG = CFG.get("PRODUCTS", [])  
        START_CFG = CFG.get("START", START_CFG or {})  
        SHOW_QR = bool(CFG.get("SHOW_QR", True))
        STRICT_CALLBACK_SIGN_VERIFY = bool(CFG.get("STRICT_CALLBACK_SIGN_VERIFY", True))
        ENABLE_PAYMENT_SCREENSHOT = bool(CFG.get("ENABLE_PAYMENT_SCREENSHOT", True))
        # ✅ 修复：从PAYMENTS中读取TOKEN188配置
        TOKEN188_CFG = PAYCFG.get("usdt_token188", {})
        await update.message.reply_text("配置已重新加载（已取消商品同步，主页设置以数据库为准）。")
    except Exception as e:
        await update.message.reply_text(f"重新加载失败：{e}")

application.add_handler(CommandHandler("reloadcfg", cmd_reloadcfg))


async def on_start(app: Application):
    app.job_queue.run_repeating(job_cancel_expired, interval=60, first=10)
    # 设置全局命令菜单，替换旧的 /open_shop 为 /support
    try:
        await app.bot.set_my_commands([
            BotCommand("start", "开始"),
            BotCommand("support", "联系客服"),
            BotCommand("admin", "管理员"),
        ])
    except Exception:
        pass


application.post_init = on_start


def run_flask():
    serve(app, listen="0.0.0.0:58001")

def _verify_token188_sign(params: dict, key: str) -> bool:
    """验证TOKEN188 USDT支付回调签名"""
    if not key:
        return False
    
    # 获取回调中的签名
    recv_sign = (params.get("sign") or "").strip()
    if not recv_sign:
        return False
    
    # 组装参数（排除sign）
    sign_params = {}
    for k, v in params.items():
        if k != "sign" and str(v).strip():  # 排除sign和空值
            sign_params[k] = str(v).strip()
    
    # 按ASCII码排序
    sorted_params = sorted(sign_params.items())
    
    # 拼接字符串
    param_str = "&".join([f"{k}={v}" for k, v in sorted_params])
    
    # 添加密钥
    sign_str = param_str + "&key=" + key
    
    # MD5签名
    import hashlib
    calc_sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()
    
    return recv_sign.upper() == calc_sign


@app.route("/callback", methods=["GET", "POST"])
def pay_callback():
    try:
        # IP频率限制
        client_ip = request.remote_addr or request.headers.get('X-Real-IP') or request.headers.get('X-Forwarded-For', '').split(',')[0]
        allowed, error_msg = check_ip_rate_limit(client_ip, 'ip_callback')
        if not allowed:
            print(f"⚠️ IP频率限制: {client_ip} - {error_msg}")
            return "rate_limit", 429
        
        # 检查是否为TOKEN188 USDT回调
        content_type = request.headers.get('Content-Type', '')
        if 'application/json' in content_type:
            # TOKEN188 USDT回调处理
            try:
                json_data = request.get_json()
                if json_data and 'transactionId' in json_data and 'chainType' in json_data:
                    return handle_token188_callback(json_data)
            except Exception:
                pass
        
        # 传统易支付回调处理
        params = dict(request.values) if request else {}
        out_trade_no = (params.get("out_trade_no") or "").strip()
        if not out_trade_no:
            return "bad_req", 400

        # 仅在严格模式下进行严谨验签与字段校验
        if STRICT_CALLBACK_SIGN_VERIFY:
            # 1) 通过 type + pid 精确定位商户配置，再验签；如找不到，回落为遍历尝试
            t = (params.get("type") or "").strip()
            pid = str(params.get("pid") or "").strip()
            verified = False
            try:
                # 使用新的统一签名验证函数
                verified = _verify_callback_signature(params, PAYCFG)
            except Exception:
                verified = False
            if not verified:
                return "bad_sign", 400

            # 2) trade_status 必须为成功（官方：TRADE_SUCCESS）
            trade_status = (params.get("trade_status") or "").strip().upper()
            if trade_status not in ("TRADE_SUCCESS",):
                return "bad_status", 400

        # 3) 订单必须存在，金额需匹配
        money_cb = (params.get("money") or "").strip()
        try:
            money_cb_val = round(float(money_cb), 2)
        except Exception:
            money_cb_val = None

        # 独立连接，避免与主线程竞争
        conn_cb = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur_cb = conn_cb.cursor()
        try:
            cur_cb.execute("PRAGMA busy_timeout=5000;")
        except Exception:
            pass
        try:
            row = cur_cb.execute("SELECT amount FROM orders WHERE out_trade_no=?", (out_trade_no,)).fetchone()
            if not row:
                return "no_order", 400
            amount_order = round(float(row[0]), 2)
            if money_cb_val is None or amount_order != money_cb_val:
                return "bad_amount", 400
            _mark_paid_and_deliver(out_trade_no, conn_override=conn_cb, cur_override=cur_cb)
        finally:
            try:
                cur_cb.close()
            except Exception:
                pass
            try:
                conn_cb.close()
            except Exception:
                pass
        return "success"
    except Exception:
        return "error", 500


def handle_token188_callback(json_data):
    """处理TOKEN188 USDT支付回调"""
    try:
        # 检查TOKEN188是否启用
        if not TOKEN188_CFG.get("enabled", False):
            return "token188_disabled", 400
            
        # 从配置文件读取TOKEN188配置
        TOKEN188_MERCHANT_ID = TOKEN188_CFG.get("merchant_id", "")
        TOKEN188_KEY = TOKEN188_CFG.get("key", "")
        TOKEN188_MONITOR_ADDRESS = TOKEN188_CFG.get("monitor_address", "")
        
        # 验证必要字段
        required_fields = ['amount', 'merchantId', 'to', 'transactionId', 'sign']
        for field in required_fields:
            if field not in json_data:
                print(f"TOKEN188 callback missing field: {field}")
                return "missing_field", 400
        
        # 验证商户ID
        if str(json_data.get('merchantId')) != TOKEN188_MERCHANT_ID:
            print(f"TOKEN188 invalid merchant: {json_data.get('merchantId')} != {TOKEN188_MERCHANT_ID}")
            return "invalid_merchant", 400
        
        # 验证接收地址
        if str(json_data.get('to')) != TOKEN188_MONITOR_ADDRESS:
            print(f"TOKEN188 invalid address: {json_data.get('to')} != {TOKEN188_MONITOR_ADDRESS}")
            return "invalid_address", 400
        
        # 验证签名
        if not _verify_token188_sign(json_data, TOKEN188_KEY):
            print(f"TOKEN188 invalid sign: {json_data.get('sign')}")
            return "invalid_sign", 400
        
        # 获取交易信息
        amount = float(json_data.get('amount', 0))
        transaction_id = str(json_data.get('transactionId', ''))
        from_address = str(json_data.get('from', ''))
        
        # 根据金额查找对应的订单
        # 这里需要实现根据金额匹配订单的逻辑
        conn_cb = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur_cb = conn_cb.cursor()
        
        try:
            cur_cb.execute("PRAGMA busy_timeout=5000;")
            
            # ✅ 修复：查找金额匹配且状态为pending的TOKEN188订单
            rows = cur_cb.execute(
                "SELECT out_trade_no, amount FROM orders WHERE status='pending' AND payment_method='usdt_token188' AND ABS(amount - ?) < 0.01 ORDER BY create_time DESC",
                (amount,)
            ).fetchall()
            
            if not rows:
                print(f"TOKEN188 no matching order for amount: {amount}")
                return "no_matching_order", 400
            
            # 取最新的匹配订单
            out_trade_no, order_amount = rows[0]
            
            # 记录交易信息到数据库（可选）
            try:
                cur_cb.execute(
                    "INSERT OR IGNORE INTO usdt_transactions (out_trade_no, transaction_id, from_address, amount, create_time) VALUES (?, ?, ?, ?, ?)",
                    (out_trade_no, transaction_id, from_address, amount, int(time.time()))
                )
                conn_cb.commit()  # 提交事务
            except Exception:
                pass  # 表可能不存在，忽略错误
            
            # 标记订单为已支付并发货
            _mark_paid_and_deliver(out_trade_no, conn_override=conn_cb, cur_override=cur_cb)
            
            print(f"TOKEN188 callback success: order {out_trade_no}, amount {amount}, tx {transaction_id}")
            return "success"
            
        finally:
            try:
                cur_cb.close()
            except Exception:
                pass
            try:
                conn_cb.close()
            except Exception:
                pass
                
    except Exception as e:
        # 记录错误日志
        print(f"TOKEN188 callback error: {e}")
        return "error", 500
@app.route("/health", methods=["GET"])
def health():
    try:
        cur.execute("SELECT 1").fetchone()
        return "ok"
    except Exception:
        return "error", 500

@app.route("/pay/<short_code>")
def redirect_short_link(short_code):
    """短链接重定向 - 优化版本"""
    try:
        import sqlite3
        from flask import redirect
        import os
        
        # 短链接数据库路径 - Docker环境适配
        if os.path.exists("/app"):  # Docker环境
            short_link_db = "/app/data/short_links.db"
        else:  # 本地环境
            short_link_db = os.path.join(DATA_DIR, "short_links.db")
        
        # 优化：使用更快的连接设置
        conn = sqlite3.connect(short_link_db, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        
        cur = conn.cursor()
        
        # 确保索引存在（首次运行时创建）
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_short_code ON short_links(short_code)")
            conn.commit()
        except Exception:
            pass
        
        # 优化：单次查询获取URL，异步更新点击次数
        result = cur.execute(
            "SELECT original_url FROM short_links WHERE short_code=? LIMIT 1",
            (short_code,)
        ).fetchone()
        
        if result:
            original_url = result[0]
            
            # 异步更新点击次数（不阻塞重定向）
            try:
                cur.execute(
                    "UPDATE short_links SET click_count = COALESCE(click_count, 0) + 1 WHERE short_code=?",
                    (short_code,)
                )
                conn.commit()
            except Exception:
                pass  # 点击统计失败不影响重定向
            
            conn.close()
            return redirect(original_url, code=302)
        else:
            conn.close()
            return f"链接不存在或已过期", 404
        
    except Exception as e:
        return f"服务器错误", 500

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.WARNING)
    from threading import Thread
    Thread(target=run_flask, daemon=True).start()
    if USE_WEBHOOK:
        full_webhook_url = f"{DOMAIN.rstrip('/')}" + f"{WEBHOOK_PATH}"
        application.run_webhook(
            listen="0.0.0.0",
            port=58002,
            url_path=WEBHOOK_PATH.lstrip('/'),
            webhook_url=full_webhook_url,
            secret_token=WEBHOOK_SECRET,
            drop_pending_updates=True,
            allowed_updates=("message", "callback_query", "chat_member"),
        )
    else:
        application.run_polling(
            close_loop=False,
            allowed_updates=("message", "callback_query", "chat_member"),
            drop_pending_updates=True,
            poll_interval=0,
            timeout=60,
        )

