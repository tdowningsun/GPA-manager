# GRS（Grade Rules Schema）

**GRS（Grade Rules Schema，成績規則描述規範）** 是一套開放的 JSON 規範，用於描述大專院校的 GPA 計算規則。

GRS 最初由 **GPA Manager** 專案設計，用於支援不同學校所使用的 GPA 計算制度。

透過 GRS，每所學校可以使用一份獨立的 JSON 文件描述自己的成績規則，而不需要修改軟體程式碼。

---

## 設計理念

GRS 遵循以下原則：

- 一份 JSON 文件對應一所學校。
- 使用人類可讀的 JSON 格式。
- 容易修改與維護。
- 支援版本管理。
- 儘可能保持向後相容。
- 不包含腳本或可執行程式碼。
- 不支援使用者自訂公式。

---

## 功能特色

GRS 目前支援：

- 數值成績（Numeric）
- 文字成績（Text）
- 字母成績（Letter）
- 特殊成績（Special）

數值成績支援以下計算模式：

- Range（區間模式）
- Linear（線性模式）
- Lookup（查表模式）

---

## 版本管理

GRS 使用版本化規範。

目前版本：

**GRS v1**

未來版本將以新的版本號發布，例如：

- GRS v2
- GRS v3

並盡可能保持相容性。

---

## 文件

目前提供：

- GRS v1 Specification

未來版本將提供獨立規範文件。

---

## 參考實作

GRS 的參考實作包含於 GPA Manager 專案。

GitHub:

https://github.com/tdowningsun/GPAManager

---

## 授權

GRS 作為 GPA Manager 專案的一部分，使用相同授權條款發布。
