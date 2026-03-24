#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import os
import secrets
import time
import hashlib
import requests
from io import BytesIO
from typing import Any, Dict

import qrcode
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, InputMediaPhoto, Update
from utils import render_home
from utils import send_ephemeral
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, ChatMemberHandler
from payments import create_payment as pay_create
from utils import notify_admin
from utils import build_payment_rows, get_first_enabled_payment, row_back, make_markup, rows_pay_console, build_confirm_rows
from utils import STATUS_ZH
from screenshot_utils import get_payment_screenshot

# Redis缓存和频率限制
try:
    from redis_cache import cache, get_product_cached, get_setting_cached, invalidate_product_cache
    from rate_limiter import rate_limiter, rate_limit_user_payment
    REDIS_ENABLED = True
    print("✅ Redis缓存和频率限制已启用")
except ImportError as e:
    print(f"⚠️ Redis模块未安装，缓存功能已禁用: {e}")
    REDIS_ENABLED = False
    # 定义空的装饰器
    def rate_limit_user_payment(func):
        return func

# 通过 register_user_handlers 注入的依赖
# 我们不直接从 bot.py 导入，避免循环依赖

def create_short_url(long_url, order_id):
    """创建短链接 - 使用自建短链接系统"""
    try:
        # 使用自建短链接系统
        short_url = create_self_hosted_short_link(long_url, order_id)
        if short_url:
            print(f"自建短链接生成成功: {long_url} -> {short_url}")
            return short_url
        else:
            print("短链接生成失败，返回原链接")
            return long_url
            
    except Exception as e:
        print(f"自建短链接生成失败: {e}")
        # 短链接生成失败时返回原链接，不影响支付功能
        return long_url

def generate_short_code(length=6):
    """生成随机短代码"""
    import random
    import string
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def create_self_hosted_short_link(original_url, order_id=None):
    """创建自建短链接 - 优化版本"""
    try:
        import sqlite3
        import random
        import string
        import time
        import os
        
        # 短链接数据库路径 - Docker环境适配
        if os.path.exists("/app"):  # Docker环境
            short_link_db = "/app/data/short_links.db"
        else:  # 本地环境
            # 使用相对路径避免循环导入
            base_dir = os.path.dirname(__file__)
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            short_link_db = os.path.join(data_dir, "short_links.db")
        
        # 优化：使用更快的连接设置
        conn = sqlite3.connect(short_link_db, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        
        cur = conn.cursor()
        
        # 初始化数据库和索引
        cur.execute("""
        CREATE TABLE IF NOT EXISTS short_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT UNIQUE NOT NULL,
            original_url TEXT NOT NULL,
            order_id TEXT,
            create_time INTEGER NOT NULL,
            click_count INTEGER DEFAULT 0
        )
        """)
        
        # 创建索引以提高查询性能
        cur.execute("CREATE INDEX IF NOT EXISTS idx_short_code ON short_links(short_code)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_original_url ON short_links(original_url)")
        conn.commit()
        
        # 优化：检查是否已存在（添加时间限制，避免重用过期链接）
        one_hour_ago = int(time.time()) - 3600
        existing = cur.execute(
            "SELECT short_code FROM short_links WHERE original_url=? AND create_time > ? ORDER BY create_time DESC LIMIT 1",
            (original_url, one_hour_ago)
        ).fetchone()
        
        if existing:
            short_code = existing[0]
        else:
            # 生成唯一短代码
            for attempt in range(10):
                short_code = generate_short_code()
                exists = cur.execute("SELECT 1 FROM short_links WHERE short_code=? LIMIT 1", (short_code,)).fetchone()
                if not exists:
                    break
            else:
                raise Exception("无法生成唯一短代码")
            
            # 插入数据库
            cur.execute(
                "INSERT INTO short_links (short_code, original_url, order_id, create_time, click_count) VALUES (?, ?, ?, ?, 0)",
                (short_code, original_url, order_id, int(time.time()))
            )
            conn.commit()
        
        conn.close()
        
        # 返回完整的短链接URL
        return f"https://oppkl.shop/pay/{short_code}"
        
    except Exception as e:
        # 移除调试输出，避免影响性能
        return None

def create_token188_payment(subject, amount, out_trade_no, token188_cfg, domain):
    """创建TOKEN188 USDT支付链接"""
    try:
        # 尝试使用API获取直接支付链接
        api_url = "https://payapi.188pay.net/utg/pay/address"
        
        # 从配置读取
        merchant_id = token188_cfg.get("merchant_id", "")
        key = token188_cfg.get("key", "")
        
        if not merchant_id or not key:
            return False, None, "TOKEN188商户配置不完整"
        
        # 先尝试API方式获取直接支付链接
        try:
            api_params = {
                "merchantId": merchant_id,
                "amount": str(amount),
                "out_trade_no": out_trade_no,
                "subject": subject,
                "notify_url": f"{domain}/callback",
                "timestamp": str(int(time.time()))
            }
            
            # API签名
            sorted_api_params = sorted(api_params.items())
            api_param_str = "&".join([f"{k}={v}" for k, v in sorted_api_params])
            api_sign_str = api_param_str + "&key=" + key
            api_sign = hashlib.md5(api_sign_str.encode("utf-8")).hexdigest().upper()
            api_params["sign"] = api_sign
            
            response = requests.post(api_url, json=api_params, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 200 or result.get("status") == "success":
                    direct_pay_url = result.get("pay_url") or result.get("data", {}).get("pay_url")
                    if direct_pay_url:
                        print(f"TOKEN188 API直接支付链接: {direct_pay_url}")
                        return True, direct_pay_url, None
        except Exception as e:
            print(f"TOKEN188 API调用失败，使用网关方式: {e}")
        
        # API失败，使用原始网关格式
        gateway_url = "https://payweb.188pay.net/"
        
        # 构建支付参数 - 处理中文字符
        params = {
            "pid": merchant_id,
            "type": "usdt",
            "out_trade_no": out_trade_no,
            "notify_url": f"{domain}/callback",
            "return_url": f"{domain}/",
            "name": subject,  # 中文会在后面进行URL编码
            "money": str(amount),
            "sitename": "FakaBot"
        }
        
        # 生成签名 - 按照易支付签名方式（直接加密钥）
        sorted_params = sorted(params.items())
        param_str = "&".join([f"{k}={v}" for k, v in sorted_params])
        sign_str = param_str + key  # 直接加密钥，不用&key=
        sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()  # 小写
        params["sign"] = sign
        params["sign_type"] = "MD5"
        
        # 生成支付链接 - 使用原始网关格式，确保中文正确编码
        from urllib.parse import quote
        query_params = []
        for k, v in params.items():
            # 对所有参数值进行URL编码，特别是中文字符
            encoded_value = quote(str(v), safe='')
            query_params.append(f"{k}={encoded_value}")
        query_string = "&".join(query_params)
        full_pay_url = f"{gateway_url}?{query_string}"
        
        # 根据配置决定是否使用短链接
        use_short_url = token188_cfg.get("use_short_url", False)
        print(f"TOKEN188短链接配置: use_short_url = {use_short_url}")
        print(f"TOKEN188配置内容: {token188_cfg}")
        
        if use_short_url:
            try:
                print(f"尝试生成短链接，原链接长度: {len(full_pay_url)}")
                short_url = create_short_url(full_pay_url, out_trade_no)
                if short_url:
                    print(f"短链接生成成功: {short_url}")
                    return True, short_url, None
                else:
                    print("短链接生成失败，使用原链接")
            except Exception as e:
                print(f"短链接生成异常: {e}")
                pass  # 如果短链接失败，使用原链接
        
        return True, full_pay_url, None
            
    except Exception as e:
        return False, None, f"TOKEN188支付链接生成失败: {str(e)}"


def register_user_handlers(application: Application, deps: Dict[str, Any]):
    cur = deps["cur"]
    conn = deps["conn"]
    PAYCFG = deps["PAYCFG"]
    START_CFG = deps["START_CFG"]
    SHOW_QR = deps["SHOW_QR"]
    ENABLE_PAYMENT_SCREENSHOT = deps.get("ENABLE_PAYMENT_SCREENSHOT", True)
    ORDER_TIMEOUT_SECONDS = deps["ORDER_TIMEOUT_SECONDS"]
    ADMIN_ID = deps["ADMIN_ID"]
    DOMAIN = deps["DOMAIN"]
    CLIENT_IP = deps["CLIENT_IP"]
    TOKEN188_CFG = deps.get("TOKEN188_CFG", {})
    # 严格按官方文档执行，不使用控制台回落开关

    _delete_last_and_send_text = deps["_delete_last_and_send_text"]
    _delete_last_and_send_photo = deps["_delete_last_and_send_photo"]
    _get_setting = deps["_get_setting"]
    mark_paid_and_deliver = deps.get("mark_paid_and_deliver")

    # 支付签名与下单逻辑已迁移到 payments.py，避免重复维护。

    def get_payment_timeout_seconds(channel: str) -> int:
        """
        根据支付方式返回不同的订单超时时间
        
        Args:
            channel: 支付方式标识
            
        Returns:
            int: 超时时间（秒）
        """
        timeout_config = {
            "usdt_token188": 60 * 60,      # TOKEN188支付：60分钟
            "usdt_lemon": 120 * 60,        # 柠檬USDT：120分钟
            "alipay": 10 * 60,             # 支付宝：10分钟
            "wxpay": 10 * 60,              # 微信支付：10分钟
        }
        return timeout_config.get(channel, ORDER_TIMEOUT_SECONDS)  # 默认使用配置文件中的值

    # ---------------- 用户端功能：命令与回调 ----------------

    # 简单的本地限流（按订单号）
    _recheck_cooldown: Dict[str, float] = {}

    async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        # 直接显示主页
        await render_home(
            update.effective_chat.id,
            cur,
            START_CFG,
            _get_setting,
            _delete_last_and_send_photo,
            _delete_last_and_send_text,
        )

    async def cb_show_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        try:
            await query.answer()
        except Exception:
            pass
        await render_home(
            update.effective_chat.id,
            cur,
            START_CFG,
            _get_setting,
            _delete_last_and_send_photo,
            _delete_last_and_send_text,
        )

    async def _send_support_info(chat_id: int):
        """统一发送客服信息：支持 @username/URL/数字ID 三种形式，或纯文本。
        行为与原 cb_support/cmd_support 保持一致。
        """
        try:
            s = (_get_setting("support.contact", "") or "").strip()
            if not s:
                await _delete_last_and_send_text(
                    chat_id,
                    "ℹ️ 暂未配置客服联系方式。",
                    reply_markup=make_markup([row_back("show:list")]),
                )
                return
            s_lower = s.lower()
            url = None
            if s_lower.startswith("http://") or s_lower.startswith("https://") or s_lower.startswith("tg://"):
                url = s
            elif s.startswith("@") and len(s) > 1:
                url = f"https://t.me/{s.lstrip('@')}"
            elif s.isdigit():
                url = f"tg://user?id={s}"
            if url:
                # 追加复用的返回按钮
                kb = make_markup([[InlineKeyboardButton("💁联系客服", url=url), InlineKeyboardButton("⬅️ 返回", callback_data="show:list")]])
                await _delete_last_and_send_text(chat_id, "🆘 客服\n点击下方按钮", reply_markup=kb)
            else:
                await _delete_last_and_send_text(
                    chat_id,
                    f"🆘 客服联系方式：\n{s}",
                    reply_markup=make_markup([row_back("show:list")]),
                )
        except Exception:
            try:
                await _delete_last_and_send_text(
                    chat_id,
                    "❗ 获取客服信息失败，请稍后重试。",
                    reply_markup=make_markup([row_back("show:list")]),
                )
            except Exception:
                pass

    async def cb_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        _, pid = query.data.split(":")
        row = cur.execute(
            "SELECT name, full_description, price, cover_url FROM products WHERE id=? AND status='on'",
            (pid,),
        ).fetchone()
        if not row:
            try:
                await _delete_last_and_send_text(
                    update.effective_chat.id,
                    "⚠️ 商品不存在或已下架",
                    reply_markup=make_markup([row_back("show:list")])
                )
            except Exception:
                pass
            return
        name, full_desc, price, cover = row
        img = cover
        rows = [[InlineKeyboardButton("🛒 购买", callback_data=f"buy:{pid}")], row_back("show:list")]
        kb = InlineKeyboardMarkup(rows)
        caption = f" {name}\n\n{full_desc}\n\n💰 价格：¥{price}"
        try:
            await query.edit_message_media(
                media=InputMediaPhoto(media=img, caption=caption), reply_markup=kb
            )
        except Exception:
            chat_id = update.effective_chat.id
            if img:
                try:
                    await _delete_last_and_send_photo(chat_id, img, caption=caption, reply_markup=kb)
                    return
                except Exception:
                    pass
            await _delete_last_and_send_text(chat_id, caption, reply_markup=kb)

    async def cb_support(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        try:
            await query.answer()
        except Exception:
            pass
        await _send_support_info(update.effective_chat.id)

    async def cmd_support(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """用户命令：/support 显示客服联系方式。"""
        await _send_support_info(update.effective_chat.id)

    async def cb_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        _, pid = query.data.split(":")
        row = cur.execute("SELECT name, price, cover_url FROM products WHERE id=? AND status='on'", (pid,)).fetchone()
        if not row:
            try:
                await _delete_last_and_send_text(
                    update.effective_chat.id,
                    "⚠️ 商品不存在或已下架",
                    reply_markup=make_markup([row_back("show:list")])
                )
            except Exception:
                pass
            return
        name, price, cover = row
        # 读取后台配置的列数：settings(ui.payment_cols) -> START_CFG.payment_cols -> 默认3；限定 1~4 列
        try:
            cols_raw = _get_setting("ui.payment_cols", (START_CFG.get("payment_cols") or 3))
            cols = int(cols_raw or 3)
        except Exception:
            cols = 3
        cols = max(1, min(4, cols))
        # 检查是否只有一个启用的支付方式
        first_payment = get_first_enabled_payment(PAYCFG, get_setting_func=_get_setting)
        payment_rows = build_payment_rows(PAYCFG, pid=pid, get_setting_func=_get_setting, callback_fmt="pay:{pid}:{channel}", max_cols=cols, skip_single=True)
        
        # 如果只有一个支付方式，直接跳转到支付
        if not payment_rows and first_payment:
            # 模拟支付按钮点击，直接调用支付处理逻辑
            class FakeQuery:
                def __init__(self, data):
                    self.data = data
                async def answer(self):
                    pass
            
            fake_update = Update(
                update_id=update.update_id,
                callback_query=FakeQuery(f"pay:{pid}:{first_payment}")
            )
            fake_update._effective_chat = update.effective_chat
            fake_update._effective_user = update.effective_user
            
            await cb_pay(fake_update, ctx)
            return
        
        # 多个支付方式时显示选择界面
        rows = payment_rows
        rows.append(row_back(f"detail:{pid}"))
        caption = f"商品：{name}\n价格：¥{price}\n💳 请选择支付方式："
        if cover:
            try:
                await _delete_last_and_send_photo(
                    update.effective_chat.id,
                    cover,
                    caption=caption,
                    reply_markup=make_markup(rows),
                )
                return
            except Exception:
                pass
        await _delete_last_and_send_text(
            update.effective_chat.id,
            caption,
            reply_markup=make_markup(rows),
        )

    def create_payment(channel, subject, amount, out_trade_no):
        # 检查支付方式是否启用
        payment_enabled = _get_setting(f"payment.{channel}.enabled", "true") == "true"
        if not payment_enabled:
            return False, None, f"支付方式 {channel} 已关闭"
        
        # 如果是TOKEN188 USDT支付
        if channel == "usdt_token188":
            token188_config = PAYCFG.get("usdt_token188", {})
            if token188_config.get("enabled", False):
                try:
                    return create_token188_payment(subject, amount, out_trade_no, token188_config, DOMAIN)
                except Exception as e:
                    return False, None, f"TOKEN188支付链接创建失败: {str(e)}"
        
        # 其他支付方式使用原有的易支付逻辑
        if channel not in PAYCFG:
            return False, None, f"未知支付方式 {channel}"
        ch = PAYCFG[channel]
        try:
            ok, pay_url, err = pay_create(ch, subject, amount, out_trade_no, DOMAIN, CLIENT_IP)
            return ok, pay_url, err
        except Exception as e:
            return False, None, str(e)

    async def _preload_payment_order(update: Update, ctx: ContextTypes.DEFAULT_TYPE, pid: str, channel: str):
        """后台预加载支付订单（不显示给用户）"""
        try:
            # 生成订单但不发送消息
            row = cur.execute("SELECT name, price, cover_url FROM products WHERE id=? AND status='on'", (pid,)).fetchone()
            if not row:
                return
            name, price, cover = row
            
            # 人民币通道最小金额前置校验
            try:
                rmb_channels = {"alipay", "wxpay"}
                pval = float(price)
                if channel in rmb_channels and pval < 3.0:
                    return
            except Exception:
                pass
            
            # 生成订单号
            def _rand36(k: int) -> str:
                chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                return "".join(secrets.choice(chars) for _ in range(max(1, int(k))))
            
            def _new_out_trade_no() -> str:
                prefix = _rand36(6)
                num = str(secrets.randbelow(100000)).zfill(5)
                return f"{prefix}-{num}"
            
            for _ in range(5):
                cand = _new_out_trade_no()
                try:
                    exists = cur.execute("SELECT 1 FROM orders WHERE out_trade_no=? LIMIT 1", (cand,)).fetchone()
                except Exception:
                    exists = None
                if not exists:
                    out_trade_no = cand
                    break
            else:
                out_trade_no = f"{_rand36(6)}-{str(int(time.time()))[-5:]}"
            
            # 创建支付链接
            ok, pay_url, err = create_payment(channel, name, price, out_trade_no)
            if ok:
                # ✅ 修复：立即保存到数据库，避免支付回调时找不到订单
                try:
                    cur.execute(
                        "INSERT INTO orders (user_id, product_id, amount, payment_method, out_trade_no, create_time) VALUES (?,?,?,?,?,?)",
                        (update.effective_user.id, pid, price, channel, out_trade_no, int(time.time())),
                    )
                    conn.commit()
                    
                    # 取消其他待支付订单
                    try:
                        cur.execute(
                            "UPDATE orders SET status='cancelled' WHERE user_id=? AND status='pending' AND out_trade_no<>?",
                            (update.effective_user.id, out_trade_no),
                        )
                        conn.commit()
                    except Exception:
                        pass
                    
                    # 保存到用户数据中，供后续显示使用
                    ctx.user_data["preloaded_order"] = {
                        "out_trade_no": out_trade_no,
                        "pay_url": pay_url,
                        "name": name,
                        "price": price,
                        "cover": cover,
                        "channel": channel,
                        "pid": pid
                    }
                    print(f"✅ 订单预加载成功并已保存到数据库: {out_trade_no}")
                except Exception as e:
                    print(f"❌ 订单保存到数据库失败: {e}")
                    # 保存失败则不设置预加载数据，让后续重新创建
                    return
        except Exception as e:
            print(f"❌ 订单预加载失败: {e}")

    async def cb_payment_announcement_ack(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """用户确认支付公告后，继续生成支付链接"""
        query = update.callback_query
        try:
            await query.answer("✅ 已确认")
        except Exception:
            pass
        
        # 从callback_data中获取商品ID和支付渠道
        _, pid, channel = query.data.split(":")
        
        # 检查是否有预加载的订单
        preloaded = ctx.user_data.get("preloaded_order")
        if preloaded and preloaded.get("pid") == pid and preloaded.get("channel") == channel:
            # ✅ 修复：预加载订单已经在数据库中，直接显示即可
            print(f"⚡ 使用预加载订单（已在数据库）: {preloaded['out_trade_no']}")
            
            # 显示订单（复用 _create_payment_order 中的显示逻辑）
            await _create_payment_order(update, ctx, pid, channel, use_preloaded=preloaded)
            
            # 清理预加载数据
            ctx.user_data.pop("preloaded_order", None)
            ctx.user_data.pop("pending_payment", None)
        else:
            # 预加载失败或数据不匹配，重新创建订单
            print("⚠️ 预加载订单不可用，重新创建")
            await _create_payment_order(update, ctx, pid, channel)

    @rate_limit_user_payment
    async def cb_pay(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        try:
            await query.answer()
        except Exception:
            pass
        _, pid, channel = query.data.split(":")
        
        # 检查该支付方式是否启用公告
        announcement_enabled = _get_setting(f"announcement.{channel}.enabled", "true") == "true"
        
        if announcement_enabled:
            # 根据支付方式获取对应的公告内容
            is_usdt = channel in ["usdt", "usdt_token188", "usdt_lemon"]
            
            # 获取自定义公告
            if is_usdt:
                custom_announcement = (_get_setting("announcement.usdt.text", "")).strip()
            else:
                custom_announcement = (_get_setting("announcement.alipay_wxpay.text", "")).strip()
            
            if custom_announcement:
                payment_announcement = custom_announcement
            else:
                # 根据支付方式显示不同的默认公告
                if is_usdt:
                    payment_announcement = (
                        "📢 USDT支付重要提醒\n\n\n"
                        "⚠️ 请注意手续费问题\n\n"
                        "🏦 交易所转账（火币/欧易/币安）\n"
                        "   会扣 1U 手续费\n"
                        "   商品价格 10U → 请转 11U\n"
                        "   否则到账不足，无法自动拉群\n\n"
                        "💳 钱包转账（推荐 ✅）\n"
                        "   支持 Bitpie / TP / imToken 等钱包\n"
                        "   直接按商品金额转（例：10U 转 10U）\n"
                        "   钱包自动扣矿工费，到账准确，更省钱！\n\n"
                        "⚡️ 付款即发货，1-3分钟快速到账\n"
                        "   机器人自动拉你进会员群 ✅"
                    )
                else:
                    payment_announcement = (
                        "📢 欢迎光临官方商店\n\n\n"
                        "💳 微信 / 支付宝付款说明\n\n"
                        "✅ 按提示金额准确付款即可\n"
                        "✅ 支持微信扫码、支付宝扫码\n"
                        "✅ 付款后请勿关闭页面\n\n"
                        "⚡️ 付款即发货，1-3分钟快速到账\n"
                        "   机器人自动拉你进会员群 ✅"
                    )
            
            # 保存支付信息到用户数据，用于后续处理
            ctx.user_data["pending_payment"] = {"pid": pid, "channel": channel}
            
            # 后台异步开始生成订单（不等待完成）
            asyncio.create_task(_preload_payment_order(update, ctx, pid, channel))
            
            kb = make_markup([[InlineKeyboardButton("✅ 我知道了，继续支付", callback_data=f"pay_ack:{pid}:{channel}")]])
            
            try:
                await _delete_last_and_send_text(
                    update.effective_chat.id,
                    payment_announcement,
                    reply_markup=kb
                )
            except Exception:
                pass
            return
        
        # 公告未启用，直接创建订单
        await _create_payment_order(update, ctx, pid, channel)

    async def _create_payment_order(update: Update, ctx: ContextTypes.DEFAULT_TYPE, pid: str, channel: str, use_preloaded: dict = None):
        """创建支付订单的核心逻辑"""
        row = cur.execute("SELECT name, price, cover_url FROM products WHERE id=? AND status='on'", (pid,)).fetchone()
        if not row:
            try:
                await _delete_last_and_send_text(
                    update.effective_chat.id,
                    "⚠️ 商品不存在或已下架",
                    reply_markup=make_markup([row_back("show:list")])
                )
            except Exception:
                pass
            return
        name, price, cover = row
        
        # 先显示"正在生成"提示，保持用户体验一致
        try:
            await _delete_last_and_send_text(
                update.effective_chat.id,
                "⏳ 正在生成付款链接，请稍候…\n请勿重复点击按钮，预计几秒完成。"
            )
        except Exception:
            pass
        
        # 如果使用预加载订单，直接跳到显示部分
        if use_preloaded:
            out_trade_no = use_preloaded['out_trade_no']
            pay_url = use_preloaded['pay_url']
            print(f"⚡ 直接使用预加载订单显示: {out_trade_no}")
        else:
            # 人民币通道最小金额前置校验（≥ 3.00 元）
            try:
                rmb_channels = {"alipay", "wxpay"}
                pval = float(price)
                if channel in rmb_channels and pval < 3.0:
                    await _delete_last_and_send_text(
                        update.effective_chat.id,
                        "❌ 该通道最小支付金额为 3.00 元，请返回重新选择支付方式或购买金额≥3.00 的商品。",
                        reply_markup=make_markup([row_back(f"buy:{pid}")])
                    )
                    return
            except Exception:
                pass

            # 生成 out_trade_no：6位Base36随机-5位数字（如 MJ6K3A-89899），并确保唯一性
            def _rand36(k: int) -> str:
                chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                return "".join(secrets.choice(chars) for _ in range(max(1, int(k))))

            def _new_out_trade_no() -> str:
                prefix = _rand36(6)
                num = str(secrets.randbelow(100000)).zfill(5)
                return f"{prefix}-{num}"

            # 防碰撞：最多尝试 5 次
            for _ in range(5):
                cand = _new_out_trade_no()
                try:
                    exists = cur.execute("SELECT 1 FROM orders WHERE out_trade_no=? LIMIT 1", (cand,)).fetchone()
                except Exception:
                    exists = None
                if not exists:
                    out_trade_no = cand
                    break
            else:
                # 极端情况下仍碰撞，退回到时间戳方案
                out_trade_no = f"{_rand36(6)}-{str(int(time.time()))[-5:]}"
            ok, pay_url, err = create_payment(channel, name, price, out_trade_no)
            if not ok:
                try:
                    await _delete_last_and_send_text(
                        update.effective_chat.id,
                        f"❌ 下单失败：{err}\n请稍后重试，或返回重新选择支付方式。",
                        reply_markup=make_markup([row_back(f"buy:{pid}")])
                    )
                except Exception:
                    pass
                return
            
            # ✅ 修复：检查订单是否已存在（避免重复插入）
            try:
                existing = cur.execute("SELECT 1 FROM orders WHERE out_trade_no=? LIMIT 1", (out_trade_no,)).fetchone()
                if not existing:
                    cur.execute(
                        "INSERT INTO orders (user_id, product_id, amount, payment_method, out_trade_no, create_time) VALUES (?,?,?,?,?,?)",
                        (update.effective_user.id, pid, price, channel, out_trade_no, int(time.time())),
                    )
                    conn.commit()
                    
                    # 取消其他待支付订单
                    try:
                        cur.execute(
                            "UPDATE orders SET status='cancelled' WHERE user_id=? AND status='pending' AND out_trade_no<>?",
                            (update.effective_user.id, out_trade_no),
                        )
                        conn.commit()
                    except Exception:
                        pass
                else:
                    print(f"⚠️ 订单 {out_trade_no} 已存在，跳过插入")
            except Exception as e:
                print(f"❌ 订单插入检查失败: {e}")
        try:
            row_desc = cur.execute(
                "SELECT full_description FROM products WHERE id=?",
                (pid,),
            ).fetchone()
            detail = (row_desc[0]) if (row_desc and row_desc[0]) else ""
        except Exception:
            detail = ""
        def _build_pay_kb(pid_val: str, otn: str) -> InlineKeyboardMarkup:
            return make_markup(rows_pay_console(otn))
        kb = _build_pay_kb(pid, out_trade_no)
        
        # 检查是否为TOKEN188 USDT支付
        is_token188_usdt = (channel == "usdt_token188" and PAYCFG.get("usdt_token188", {}).get("enabled", False))
        
        if is_token188_usdt:
            # TOKEN188 USDT支付显示 - 使用网页截图二维码
            method_name = "USDT(TRC20)"
            timeout_seconds = get_payment_timeout_seconds(channel)
            mins = max(1, timeout_seconds // 60)
            
            # 尝试获取支付页面截图（如果启用了截图功能）
            screenshot_img = None
            print(f"🔧 DEBUG: ENABLE_PAYMENT_SCREENSHOT = {ENABLE_PAYMENT_SCREENSHOT}")
            
            # 强制启用截图功能进行测试
            if True:  # 临时强制启用
                try:
                    print(f"🔧 正在为TOKEN188订单 {out_trade_no} 生成支付页面截图...")
                    screenshot_img = get_payment_screenshot(pay_url, use_fallback=True)
                    if screenshot_img:
                        print(f"✅ 截图生成成功，大小: {len(screenshot_img.getvalue())} bytes")
                    else:
                        print("❌ 截图生成失败，返回None")
                except Exception as e:
                    print(f"❌ TOKEN188支付页面截图异常: {e}")
                    import traceback
                    traceback.print_exc()
            
            if screenshot_img:
                # 使用截图作为支付二维码
                try:
                    screenshot_img.name = f"token188_pay_{out_trade_no}.jpg"
                    # 获取USDT支付地址
                    token188_config = PAYCFG.get("usdt_token188", {})
                    usdt_address = token188_config.get("monitor_address", "")
                    
                    caption = (
                        f"🧾 订单号：{out_trade_no}\n"
                        f"📦 商品名：{name}\n"
                        f"📝 商品详情：{detail}\n"
                        f"💰 价格：¥{price}\n"
                        f"💳 支付方式：{method_name}\n"
                        f"📍 USDT钱包地址：`{usdt_address}`\n"
                        f"⏱️ 订单有效期约 {mins} 分钟，超时将自动取消。\n\n"
                        f"提示：扫描上方二维码完成USDT支付，支付成功后请返回本聊天等待邀请链接。"
                    )
                    
                    await _delete_last_and_send_photo(
                        update.effective_chat.id,
                        InputFile(screenshot_img),
                        caption=caption,
                        reply_markup=kb,
                        parse_mode="Markdown"
                    )
                    return
                except Exception as e:
                    print(f"发送TOKEN188截图失败: {e}")
            
            # 截图失败时的备用方案：显示支付链接
            # 获取USDT支付地址
            token188_config = PAYCFG.get("usdt_token188", {})
            usdt_address = token188_config.get("monitor_address", "")
            
            caption = (
                f"🧾 订单号：{out_trade_no}\n"
                f"📦 商品名：{name}\n"
                f"📝 商品详情：{detail}\n"
                f"💰 价格：¥{price}\n"
                f"💳 支付方式：{method_name}\n"
                f"📍 USDT钱包地址：`{usdt_address}`\n"
                f"🔗 支付链接：{pay_url}\n"
                f"⏱️ 订单有效期约 {mins} 分钟，超时将自动取消。\n\n"
                f"提示：点击链接完成USDT支付，支付成功后系统会自动检测并发送邀请链接。"
            )
            
            if cover:
                try:
                    await _delete_last_and_send_photo(
                        update.effective_chat.id,
                        cover,
                        caption=caption,
                        reply_markup=kb,
                        parse_mode="Markdown"
                    )
                    return
                except Exception:
                    pass
            await _delete_last_and_send_text(update.effective_chat.id, caption, reply_markup=kb, parse_mode="Markdown")
            
        else:
            # 传统支付方式显示
            if SHOW_QR:
                qr_img = qrcode.make(pay_url)
                bio = BytesIO()
                bio.name = "qrcode.png"
                qr_img.save(bio, "PNG")
                bio.seek(0)
                await _delete_last_and_send_photo(
                    update.effective_chat.id,
                    InputFile(bio),
                    caption=(
                        f"📷 请扫码支付 ¥{price}\n"
                        f"🧾 订单号：{out_trade_no}\n"
                        f"⏱️ 订单有效期约 {max(1, get_payment_timeout_seconds(channel) // 60)} 分钟，超时将自动取消。\n"
                        f"提示：支付成功后我会自动发送自动拉群邀请链接。"
                    ),
                    reply_markup=kb,
                )
            else:
                method_name = PAYCFG.get(channel, {}).get("name", channel)
                timeout_seconds = get_payment_timeout_seconds(channel)
                mins = max(1, timeout_seconds // 60)
                
                caption = (
                    f"🧾 订单号：{out_trade_no}\n"
                    f"📦 商品名：{name}\n"
                    f"📝 商品详情：{detail}\n"
                    f"💰 价格：¥{price}\n"
                    f"💳 支付方式：{method_name}\n"
                    f"🔗 支付链接：{pay_url}\n"
                    f"⏱️ 订单有效期约 {mins} 分钟，超时将自动取消。\n\n"
                    f"提示：若链接无法直接打开，可复制到浏览器；完成支付后请返回本聊天等待邀请链接。"
                )
                if cover:
                    try:
                        await _delete_last_and_send_photo(
                            update.effective_chat.id,
                            cover,
                            caption=caption,
                            reply_markup=kb,
                        )
                        return
                    except Exception:
                        pass
                await _delete_last_and_send_text(update.effective_chat.id, caption, reply_markup=kb)

        # 供后续确认场景恢复键盘使用
        async def _restore_pay_keyboard(msg, pid_val: str, otn: str):
            try:
                await msg.edit_reply_markup(reply_markup=make_markup(rows_pay_console(otn)))
            except Exception:
                try:
                    await query.edit_message_reply_markup(reply_markup=make_markup(rows_pay_console(otn)))
                except Exception:
                    pass

    async def cb_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        try:
            await query.answer()
        except Exception:
            pass
        _, out_trade_no = query.data.split(":")
        # 旧入口保留：直接取消。新逻辑走 ask:cancel -> confirm:cancel:yes
        row = cur.execute(
            "SELECT id, status FROM orders WHERE out_trade_no=? AND user_id=?",
            (out_trade_no, update.effective_user.id),
        ).fetchone()
        if not row:
            await cb_show_list(update, ctx)
            return
        oid, status = row
        if status != "pending":
            # 只有待支付订单可取消，其它状态直接返回列表
            await cb_show_list(update, ctx)
            return
        try:
            cur.execute("UPDATE orders SET status='cancelled' WHERE id=? AND status='pending'", (oid,))
            conn.commit()
        except Exception:
            pass
        chat_id = update.effective_chat.id
        try:
            await send_ephemeral(application.bot, chat_id, "✅ 已取消订单，正在返回商品列表…", ttl=2)
        except Exception:
            pass
        await cb_show_list(update, ctx)

    async def cb_ask_leave(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        try:
            await query.answer()
        except Exception:
            pass
        parts = query.data.split(":")
        # ask:cancel:OTN or ask:back:PID:OTN
        if len(parts) < 3:
            return
        kind = parts[1]
        if kind == "cancel":
            otn = parts[2]
            kb = make_markup(build_confirm_rows(
                yes_cb=f"confirm:cancel:{otn}:yes",
                no_cb=f"confirm:cancel:{otn}:no",
                yes_label="✅ 确定取消",
                no_label="↩️ 继续付款",
            ))
            try:
                await query.edit_message_reply_markup(reply_markup=kb)
            except Exception:
                pass
            return
        if kind == "back":
            if len(parts) < 4:
                return
            pid_val, otn = parts[2], parts[3]
            kb = make_markup(build_confirm_rows(
                yes_cb=f"confirm:back:{pid_val}:{otn}:yes",
                no_cb=f"confirm:back:{pid_val}:{otn}:no",
                yes_label="✅ 确定离开",
                no_label="↩️ 留在付款台",
            ))
            try:
                await query.edit_message_reply_markup(reply_markup=kb)
            except Exception:
                pass
            return

    async def cb_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        try:
            await query.answer()
        except Exception:
            pass
        parts = query.data.split(":")
        # confirm:cancel:OTN:yes/no  or confirm:back:PID:OTN:yes/no
        if len(parts) < 4:
            return
        kind = parts[1]
        if kind == "cancel":
            otn, ans = parts[2], parts[3]
            if ans == "yes":
                # 直接执行取消并返回主页：删除当前确认消息并展示首页
                # 1) 尝试取消订单
                try:
                    row = cur.execute(
                        "SELECT id, status FROM orders WHERE out_trade_no=? AND user_id=?",
                        (otn, update.effective_user.id),
                    ).fetchone()
                except Exception:
                    row = None
                if row:
                    oid, status = row
                    if status == "pending":
                        try:
                            cur.execute("UPDATE orders SET status='cancelled' WHERE id=? AND status='pending'", (oid,))
                            conn.commit()
                        except Exception:
                            pass
                # 2) 删除确认消息
                try:
                    msg = getattr(query, "message", None)
                    if msg is not None:
                        await application.bot.delete_message(chat_id=msg.chat_id, message_id=msg.message_id)
                except Exception:
                    pass
                # 3) 直接渲染首页（使用公共渲染函数）
                await render_home(
                    update.effective_chat.id,
                    cur,
                    START_CFG,
                    _get_setting,
                    _delete_last_and_send_photo,
                    _delete_last_and_send_text,
                )
            else:
                # 用户选择“不取消”，仅恢复当前消息的付款键盘，避免界面消失
                try:
                    await query.edit_message_reply_markup(reply_markup=make_markup(rows_pay_console(otn)))
                except Exception:
                    pass
            return
        if kind == "back":
            if len(parts) < 5:
                return
            pid_val, otn, ans = parts[2], parts[3], parts[4]
            if ans == "yes":
                # 返回上一页（支付方式选择）：构造带有异步 answer() 的伪回调
                class _Q:
                    def __init__(self, data: str):
                        self.data = data
                    async def answer(self):
                        return
                update.callback_query = _Q(f"buy:{pid_val}")
                await cb_buy(update, ctx)
            else:
                # 恢复原付款台键盘
                try:
                    await query.edit_message_reply_markup(reply_markup=make_markup(rows_pay_console(otn)))
                except Exception:
                    pass
            return

    async def cb_recheck(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        try:
            await query.answer()
        except Exception:
            pass
        _, out_trade_no = query.data.split(":")
        now = time.time()

        # 限流：同一订单10秒内最多一次
        ts = _recheck_cooldown.get(out_trade_no, 0)
        if now - ts < 10:
            await send_ephemeral(application.bot, update.effective_user.id, "⏳ 操作过于频繁，请稍后再试…")
            return
        _recheck_cooldown[out_trade_no] = now

        row = cur.execute(
            "SELECT id, user_id, product_id, status, create_time, payment_method FROM orders WHERE out_trade_no=?",
            (out_trade_no,)
        ).fetchone()
        if not row:
            await send_ephemeral(application.bot, update.effective_user.id, "未找到该订单，请返回重试。")
            return
        oid, uid, pid, status, create_ts, payment_method = row
        # 仅允许下单用户查询
        if int(uid) != int(update.effective_user.id):
            await send_ephemeral(application.bot, update.effective_user.id, "❌ 无权操作此订单")
            return

        # 如果已支付/完成，根据商品发货方式处理：卡密或自动拉群
        if status in ("paid", "completed"):
            # 查询商品发货方式
            try:
                prow = cur.execute("SELECT deliver_type, name, card_fixed FROM products WHERE id=?", (pid,)).fetchone()
            except Exception:
                prow = None
            deliver_type, pname, card_fixed_val = (prow[0] if prow else None), (prow[1] if prow else "商品"), (prow[2] if prow else None)
            dt = (deliver_type or 'join_group').strip().lower()

            if dt in ("card_fixed", "card_pool"):
                # 卡密类商品
                if status == "completed":
                    # 重发卡密
                    try:
                        if dt == "card_fixed":
                            card_text = (card_fixed_val or "").strip()
                        else:
                            row_key = cur.execute("SELECT key_text FROM card_keys WHERE used_by_order_id=? LIMIT 1", (oid,)).fetchone()
                            card_text = (row_key[0] if row_key else None)
                        if card_text:
                            msg = (
                                f"✅ 已确认支付成功\n"
                                f"📦 商品：{pname}\n"
                                f"🔐 您的卡密：\n{card_text}\n\n"
                                f"如已保存可忽略本消息。"
                            )
                            await _delete_last_and_send_text(uid, msg)
                            return
                    except Exception:
                        pass
                    # 未查到卡密，提示管理员
                    try:
                        await notify_admin(application.bot, f"[重发失败-未找到卡密] oid={oid} pid={pid}", ADMIN_ID, prefix="")
                    except Exception:
                        pass
                    await _delete_last_and_send_text(uid, f"✅ 已支付，但暂未找到卡密记录，请稍后再试或联系管理员。")
                    return
                else:
                    # status == paid：触发发卡
                    try:
                        if callable(mark_paid_and_deliver):
                            mark_paid_and_deliver(out_trade_no)
                    except Exception:
                        pass
                    await _delete_last_and_send_text(uid, f"✅ 已检测到支付成功：{pname}\n系统正在为您发卡，请稍后再次点击“重新检查”。")
                    return

            # 非卡密类：沿用自动拉群邀请逻辑
            nowi = int(time.time())
            inv = cur.execute(
                "SELECT invite_link, expire_time, revoked FROM invites WHERE order_id=? AND expire_time>=? AND revoked=0 ORDER BY id DESC LIMIT 1",
                (oid, nowi)
            ).fetchone()
            if inv:
                invite_link, expire_at, _rv = inv
                mins = max(1, (expire_at - nowi) // 60)
                msg = (
                    "✅ 已确认支付成功\n"
                    f"这是您的自动拉群邀请链接（约{mins}分钟内有效，且仅可使用一次）：\n\n{invite_link}\n\n"
                    "请尽快点击加入群组。加入成功后我会自动撤销该链接。"
                )
                try:
                    await _delete_last_and_send_text(uid, msg)
                except Exception:
                    pass
                return
            # 已支付但尚未生成邀请
            wait_msg = (
                f"✅ 已检测到订单状态：{status}\n"
                f"商品：{pname}\n"
                "邀请链接生成中，请稍等片刻（通常数秒内），稍后再点一次“重新检查”。"
            )
            try:
                await _delete_last_and_send_text(uid, wait_msg)
            except Exception:
                pass
            # 通知管理员人工排查
            try:
                await notify_admin(application.bot, f"[用户催发邀请] uid={uid} out_trade_no={out_trade_no} status={status}", ADMIN_ID, prefix="")
            except Exception:
                pass
            return

        # pending 状态：检查是否超时
        if status == "pending":
            timeout_seconds = get_payment_timeout_seconds(payment_method or "")
            if int(time.time()) - int(create_ts or 0) > timeout_seconds:
                try:
                    cur.execute("UPDATE orders SET status='cancelled' WHERE id=? AND status='pending'", (oid,))
                    conn.commit()
                except Exception:
                    pass
                try:
                    await _delete_last_and_send_text(
                        uid,
                        "⏱️ 订单已超时并取消，请返回重新下单。",
                        reply_markup=make_markup([row_back("show:list")]),
                    )
                except Exception:
                    pass
                return
            await send_ephemeral(application.bot, uid, "尚未检测到支付成功，请完成支付后再点“🔄 我已支付，重新检查”。")
            return

        # 其他状态
        def _status_zh(st: str) -> str:
            """将订单状态英文映射为中文提示（使用全局常量）。"""
            return STATUS_ZH.get(str(st).lower(), str(st))
        try:
            await _delete_last_and_send_text(uid, f"当前订单状态：{_status_zh(status)}")
        except Exception:
            pass
        return

    async def on_chat_member_update(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        try:
            cmu = update.chat_member
            if cmu is None:
                return
            new = cmu.new_chat_member
            old = cmu.old_chat_member
            new_status = getattr(new, "status", None)
            if new_status not in ("member", "administrator", "creator"):
                return
            joined_uid = getattr(getattr(cmu, "new_chat_member", None), "user", None)
            joined_uid = joined_uid.id if joined_uid is not None else None
            group_id_ctx = getattr(getattr(cmu, "chat", None), "id", None)
            inv = getattr(cmu, "invite_link", None)
            invite_url = inv.invite_link if inv and getattr(inv, "invite_link", None) else None
            row = None
            if invite_url:
                row = cur.execute(
                    "SELECT id, order_id, user_id, group_id, revoked, invite_link FROM invites WHERE invite_link=?",
                    (invite_url,),
                ).fetchone()
            if not row and joined_uid and group_id_ctx:
                try:
                    row = cur.execute(
                        "SELECT id, order_id, user_id, group_id, revoked, invite_link FROM invites "
                        "WHERE user_id=? AND group_id=? AND revoked=0 AND expire_time>=? "
                        "ORDER BY id DESC LIMIT 1",
                        (int(joined_uid), str(group_id_ctx), int(time.time())),
                    ).fetchone()
                    if row:
                        invite_url = row[5]
                except Exception:
                    row = None
            if not row:
                return
            iid, order_id, target_uid, group_id, revoked, _row_link = row
            try:
                gid_int = int(group_id)
            except Exception:
                gid_int = group_id
            if revoked:
                return
            if joined_uid and int(joined_uid) != int(target_uid):
                # 先标记为已撤销，避免数据不一致
                cur.execute("UPDATE invites SET revoked=1 WHERE id= ?", (iid,))
                conn.commit()
                try:
                    # 尝试撤销邀请链接
                    await application.bot.revoke_chat_invite_link(chat_id=gid_int, invite_link=invite_url)
                except RuntimeError as e:
                    # 事件循环已关闭，静默处理（链接已在数据库中标记为撤销）
                    if 'Event loop is closed' in str(e):
                        pass
                    else:
                        try:
                            await notify_admin(application.bot, f"[撤销失败-非目标用户] chat={group_id} link={invite_url} err={e}", ADMIN_ID, prefix="")
                        except Exception:
                            pass
                except Exception as e:
                    try:
                        await notify_admin(application.bot, f"[撤销失败-非目标用户] chat={group_id} link={invite_url} err={e}", ADMIN_ID, prefix="")
                    except Exception:
                        pass
                try:
                    await notify_admin(application.bot, f"[警告] 邀请链接被非目标用户使用，已撤销。link={invite_url} 预期UID={target_uid} 实际UID={joined_uid}", ADMIN_ID, prefix="")
                except Exception:
                    pass
                return
            # 先标记为已撤销，避免数据不一致
            cur.execute("UPDATE invites SET revoked=1 WHERE id= ?", (iid,))
            conn.commit()
            
            # 尝试撤销邀请链接（异步操作，失败不影响业务）
            try:
                await application.bot.revoke_chat_invite_link(chat_id=gid_int, invite_link=invite_url)
            except RuntimeError as e:
                # 事件循环已关闭，静默处理（链接已在数据库中标记为撤销）
                if 'Event loop is closed' not in str(e):
                    try:
                        await notify_admin(application.bot, f"[撤销失败] chat={group_id} link={invite_url} err={e}", ADMIN_ID, prefix="")
                    except Exception:
                        pass
            except Exception as e:
                # 其他错误也静默处理，不影响用户体验
                try:
                    # 只记录非事件循环错误
                    if 'Event loop' not in str(e):
                        await notify_admin(application.bot, f"[撤销失败] chat={group_id} link={invite_url} err={e}", ADMIN_ID, prefix="")
                except Exception:
                    pass
            
            name = None
            try:
                prow = cur.execute(
                    "SELECT name FROM products WHERE id=(SELECT product_id FROM orders WHERE id=?)",
                    (order_id,),
                ).fetchone()
                if prow:
                    name = prow[0]
            except Exception:
                pass
            out_trade_no = None
            amount = None
            method_key = None
            try:
                cur.execute("UPDATE orders SET status='completed' WHERE id=?", (order_id,))
                conn.commit()
                row_order = cur.execute("SELECT out_trade_no, amount, payment_method FROM orders WHERE id=?", (order_id,)).fetchone()
                if row_order:
                    out_trade_no, amount, method_key = row_order
            except Exception:
                pass
            method_name = PAYCFG.get(str(method_key or ''), {}).get('name', str(method_key or ''))
            amt_text = f"¥{amount}" if amount is not None else "(未知)"
            uname = ""
            try:
                uobj = getattr(getattr(cmu, "new_chat_member", None), "user", None)
                if uobj and getattr(uobj, "username", None):
                    uname = f"@{uobj.username}"
            except Exception:
                pass
            try:
                title = name or "群组"
                user_msg = (
                    f"🎉 已成功进群：{title}\n"
                    f"🔒 一次性邀请链接将自动撤销\n"
                    f"✅ 订单已完成 感谢支持！！！"
                )
                await _delete_last_and_send_text(target_uid, user_msg)
            except Exception:
                pass
            try:
                admin_msg = (
                    f"[成交通知]\n"
                    f"商品：{title}，金额：{amt_text}\n"
                    f"用户ID：{target_uid} 用户名：{uname}\n"
                    f"支付方式：{method_name}\n"
                    f"[订单完成] 用户已经成功入群\n"
                    f"{out_trade_no or ''}"
                )
                await notify_admin(application.bot, admin_msg, ADMIN_ID, prefix="")
            except Exception:
                pass
        except Exception:
            pass

    # 注册 handlers（用户端）
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("support", cmd_support))
    application.add_handler(CallbackQueryHandler(cb_detail, pattern=r"^detail:"))
    application.add_handler(CallbackQueryHandler(cb_support, pattern=r"^support$"))
    application.add_handler(CallbackQueryHandler(cb_buy, pattern=r"^buy:"))
    application.add_handler(CallbackQueryHandler(cb_payment_announcement_ack, pattern=r"^pay_ack:"))
    application.add_handler(CallbackQueryHandler(cb_pay, pattern=r"^pay:"))
    application.add_handler(CallbackQueryHandler(cb_cancel, pattern=r"^cancel:"))
    application.add_handler(CallbackQueryHandler(cb_ask_leave, pattern=r"^ask:(cancel|back):"))
    application.add_handler(CallbackQueryHandler(cb_confirm, pattern=r"^confirm:(cancel|back):"))
    application.add_handler(CallbackQueryHandler(cb_recheck, pattern=r"^recheck:"))
    application.add_handler(CallbackQueryHandler(cb_show_list, pattern=r"^show:list$"))
    application.add_handler(ChatMemberHandler(on_chat_member_update, ChatMemberHandler.CHAT_MEMBER))

