---
name: wechat-article-reader
description: 直接读取用户提供的微信公众号文章链接，提取正文、标题和图片位置；用于阅读、讲解和核查文章内容。
---

# 微信公众号正文直读

读取已知 `mp.weixin.qq.com` 链接，不调用 DeepSeek 或其他付费抓取、搜索、转录 API，不读取 API 密钥。搜索发现新资料属于其他任务；不要为阅读已给链接额外搜索。

## 直接读取

使用标准库脚本，结果写入新目录，不覆盖已有材料：

```powershell
python -X utf8 "<skill-dir>/scripts/read_article.py" --url "https://mp.weixin.qq.com/s/文章标识" --output-dir "<任务目录>/article-唯一标识"
```

脚本保存来源 HTML、正文纯文本和包含标题、来源、图片顺序、内容哈希的 JSON。`status=ok` 才表示提取到文章；HTTP 200、网页标题或搜索摘要都不等同于正文读取成功。图片只记录原始地址和位置，不把图片内文字、视频或评论冒充已读取内容。

## 浏览器备用读取

如果结果是 `needs_browser`，保留失败记录，使用可用浏览器工具（如 Tabbit）正常打开原链接。检查 `#js_content`、`#activity-name`、`#js_name`；读取正文 `innerText`、图片的 `data-src/src` 和页面 URL。长正文分段取完，确认没有截断。

- 直接请求被拦但浏览器正常显示文章时，可从浏览器导出 `document.documentElement.outerHTML` 到任务目录，然后复用脚本：

  ```powershell
  python -X utf8 "<skill-dir>/scripts/read_article.py" --url "<来源链接>" --html-file "<导出的DOM.html>" --output-dir "<新的结果目录>"
  ```

- 标明这是浏览器渲染后的 DOM，不是服务器原始响应；不从失效页面推断文章已删除。
- 浏览器仍显示验证码、登录或访问限制时，停止该来源，说明能读到的范围。可使用用户另行提供的正文、截图或导出文件；不绕过验证，不悄悄切回付费接口。
- 不启动登录、不改登录态，不发布、收藏、评论或迁移到飞书。用户另行要求归档时再使用对应归档能力。

## 交付

解释与原文分开，区分作者声称、截图/视频证据和独立核验。给文章原链接；明确缺失的图片文字、视频和评论。内容为空、只提取到挑战页、浏览器输出截断时，不声称已经阅读全文。
