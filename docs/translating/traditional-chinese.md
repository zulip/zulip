# Traditional Chinese translation style guide (繁體中文翻譯指南)

## Note (前言)

This guide is for the Traditional Chinese (`zh_Hant`) translation of
Zulip. It follows the usage of Taiwan, and borrows terms that users in
Taiwan already know from apps like LINE, Facebook, and Gmail. The
[Chinese translation style guide](chinese.md) covers Simplified
Chinese. Some of its decisions apply here too, but the vocabulary used
in Taiwan often differs (for example, 訊息 rather than 消息, and 使用者
rather than 用戶).

Most of the terms below record the translation that the existing
Traditional Chinese strings already use most often, as of
November 2026. If you want to change one of these decisions, please
discuss it in the #translation channel of the [Zulip development
community](https://zulip.com/development-community/) first. Then update
this guide and the [Weblate
glossary](https://hosted.weblate.org/projects/zulip/glossary/zh_Hant/)
together, so that translators don't switch the same strings back and
forth.

本指南適用於 Zulip 的繁體中文（zh_Hant）翻譯，以台灣用語為準，並參考台灣使用者熟悉的 LINE、Facebook、Gmail 等軟體用語。簡體中文請參考[中文翻譯指南](chinese.md)。兩者有些決定相通，但台灣的用語常有不同，例如用「訊息」而不用「消息」，用「使用者」而不用「用戶」。

下列術語大多記錄現行繁中譯文中最常用的譯法（截至 2026 年 11 月）。如果想改變其中某個決定，請先到 Zulip 開發社群的 #translation 頻道討論，再同時更新本指南和 Weblate 詞彙表，避免譯者來回修改同一批字串。

## General rules (通用原則)

- Address the user as **您**, not 你.

  稱呼使用者用「您」，不用「你」。

- Use full-width Chinese punctuation (，。：；？！（）), and 「」 for
  quotation marks.

  使用全形中文標點符號，引號用「」。

- Put a half-width space between Chinese text and Latin letters,
  numbers, or placeholders, for example `Zulip 組織` and
  `{count} 則訊息`.

  中文與英文字母、數字、變數之間加半形空格，例如 `Zulip 組織`、`{count} 則訊息`。

- Around HTML tags like `<z-link>`, follow the English source. Where
  the source has a space or punctuation next to a tag and the
  translation has a Chinese character in that position, put a
  half-width space between them, for example
  `您的 <z-link>綜合動態</z-link> 中已無更多訊息。`. This keeps
  Weblate's check for characters around XML tags passing.

  HTML 標籤（例如 `<z-link>`）兩側照英文原文處理：原文在標籤旁是空格或標點，而譯文在同一位置是中文字時，中間加一個半形空格，例如 `您的 <z-link>綜合動態</z-link> 中已無更多訊息。`。這樣才能通過 Weblate 的「XML 標籤周圍的字元」檢查。

- Use the measure word 則 for messages, 位 for users, and 個 for
  channels and files.

  量詞：訊息用「則」，使用者用「位」，頻道和檔案用「個」。

- In error messages, prefer 無法 over 不能, and keep a calm tone that
  doesn't blame the user.

  錯誤訊息用「無法」而不用「不能」，語氣平和，避免責怪使用者。

- Chinese has no plural forms. In plural strings like
  `{N, plural, one {...} other {...}}`, keep the structure and use the
  same text in both branches, as the existing translations do.

  中文沒有複數形。遇到 `{N, plural, one {...} other {...}}` 這類字串，保留原有結構，兩個分支填入相同的譯文。

## Terms (術語)

### Messages and channels (訊息與頻道)

- Message - **訊息**

  Not 消息 or 信息, which are used in mainland China.

  不用「消息」或「信息」（中國大陸用語）。

- Channel - **頻道**

- Topic - **話題**

  This matches the Simplified Chinese translation (话题). 議題 suggests
  an agenda item or a social issue, and 主題 is used for the color
  theme (淺色主題, 深色主題). Some older strings used 議題; they were
  changed to 話題 in November 2026.

  與簡體中文的「话题」一致。「議題」帶有會議議程或社會議題的意味，「主題」則用於佈景主題（淺色主題、深色主題）。部分舊譯文曾用「議題」，已於 2026 年 11 月統一改為「話題」。

- Direct message - **私人訊息**; DM - **私訊**; Group DM - **群組私訊**

  Follow the English string. When it spells out "direct message", use
  私人訊息. When it uses the abbreviation "DM", use the shorter 私訊,
  which is also the common word for this on Facebook and Instagram in
  Taiwan.

  依原文而定：原文寫出完整的「direct message」時譯為「私人訊息」；原文用縮寫「DM」時譯為較短的「私訊」，這也是台灣 Facebook、Instagram 的常見說法。

- Public channel - **公開頻道**

- Private channel - **封閉頻道**

  私人 is already used for direct messages (私人訊息), so 封閉 keeps
  the two concepts apart.

  「私人」已用於私人訊息，用「封閉」可以和私人訊息區分。

- Web-public channel - **網路公共頻道**

  This keeps it distinct from 公開頻道 (public channel).

  與「公開頻道」區分。

- Inbox - **收件匣**

- Combined feed - **綜合動態**

- Recent conversations - **最近對話**

- Drafts - **草稿**

- Compose - **撰寫**; Compose box - **撰寫框**

  編輯 is used for editing a message that was already sent (編輯訊息),
  so 撰寫 avoids confusing the two.

  「編輯」用於編輯已送出的訊息（編輯訊息），用「撰寫」可避免混淆。

- Narrow to - **縮小範圍至**

- Search - **搜尋**; Filter - **篩選**

- Mention - **提及**

- Star / Unstar - **加上星號 / 取消星號**; Starred messages -
  **星標訊息**

- Emoji - **表情符號**; Emoji reaction - **表情符號回應**

- Mark as resolved - **標註為已解決**

- Alert words - **提醒關鍵字**

- Read receipts - **已讀回條**

### Organizations and users (組織與使用者)

- Organization - **組織**

  Not 機構.

  不用「機構」。

- Demo organization - **試用組織**

  A demo organization is for trying out Zulip, and is deleted
  automatically unless it's converted into a permanent organization.
  試用 conveys this better than Demo or 示範.

  試用組織供使用者試用 Zulip，除非轉換為永久組織，否則會自動刪除。「試用」比「Demo」或「示範」更能傳達這個意思。

- User - **使用者**

  Not 用戶, which is used in mainland China.

  不用「用戶」（中國大陸用語）。

- Member - **成員**; Full member - **正式成員**

- Guest - **訪客**

- Moderator - **版主**

- Administrator - **管理員**

- Owner - **擁有者**

- Bot - **機器人**

- User group - **使用者群組**

- Profile - **個人檔案**

  In Taiwan, 設定檔 usually means a configuration file, and Zulip
  already uses it that way.

  「設定檔」在台灣通常指設定檔案（configuration file），Zulip 也已用於這個意思。

### Actions (動作)

- Subscribe / Unsubscribe - **訂閱 / 取消訂閱**

- Mute / Unmute - **靜音 / 取消靜音**

- Follow / Unfollow (a topic) - **追蹤 / 取消追蹤**

- Report (a message) - **檢舉**

  Facebook, Instagram, and LINE use 檢舉 for reporting inappropriate
  content, so users in Taiwan recognize it. 回報 suggests reporting a
  bug or a problem.

  台灣的 Facebook、Instagram、LINE 都用「檢舉」表示檢舉不當內容，使用者一看就懂；「回報」則較像回報錯誤或問題。

- Deactivate / Reactivate - **停用 / 重新啟用**

- Archive (a channel) - **封存**

- Import / Export - **匯入 / 匯出**

- Upload / Download - **上傳 / 下載**

- Log in / Log out / Sign up - **登入 / 登出 / 註冊**

### Other terms (其他)

- Integration - **整合**

- Linkifier - **連結轉換器**

- Code playground - **程式碼測試場**

- Saved snippet - **儲存的文字片段**

- Moderation requests - **審核請求**

- API key - **API 金鑰**

- Email - **電子郵件**

- Self-hosted - **自託管**

- Settings - **設定**; Preferences - **偏好設定**

- Notification - **通知**

- Invalid - **無效的**
