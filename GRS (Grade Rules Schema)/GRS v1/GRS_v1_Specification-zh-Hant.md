# GRS v1 規範

## Grade Rules Schema (GRS)

版本：1.0

---

# 1. 簡介

GRS（Grade Rules Schema，成績規則描述規範）v1 是 Grade Rules Schema 的第一個版本規範

GRS 定義了一套標準化 JSON 格式，用於描述不同學校所使用的成績制度與 GPA 計算規則

透過 GRS，軟體可以在不修改程式碼的情況下，支援不同學校的 GPA 計算方式

每一份 GRS 文件僅描述一所學校的成績規則

一個 JSON 文件代表一所學校

---

# 2. 適用範圍

GRS v1 用於描述大專院校及教育機構常見的成績制度

GRS v1 支援：

- 數值成績制度（Numeric）
- 文字成績制度（Text）
- 字母成績制度（Letter）
- 特殊成績處理（Special）

GRS v1 不負責定義：

- 課程學分計算方式
- GPA 加權方式
- 使用者自訂公式
- 程式腳本
- 自動猜測規則

GRS 僅負責描述成績規則

如何使用這些規則，由軟體實作決定

---

# 3. 核心設計原則

## 3.1 一份文件 = 一所學校

每一份 GRS 文件只能描述一所學校

例如：

```
學校 A
    |
    └── gpa_scale.json


學校 B
    |
    └── gpa_scale.json
```

一份 GRS 文件不得包含多所學校的規則

---

## 3.2 宣告式設定

GRS 文件只包含資料

不得包含：

- 程式碼
- 腳本
- 自訂函式
- 可執行運算式

---

## 3.3 版本化規範

每一份 GRS 文件必須聲明所使用的規範版本

例如：

```json
{
    "version": "1.0"
}
```

---

# 4. 文件結構

一份有效的 GRS v1 文件包含以下主要物件：

```json
{
    "metadata": {},
    "supported_inputs": {},
    "numeric": {},
    "text": {},
    "letter": {},
    "special": {}
}
```

---

# 5. metadata

`metadata` 物件包含學校資訊以及 GRS 文件資訊

範例：

```json
{
    "metadata": {
        "school": "Example University",
        "country": "Example Country",
        "version": "1.0",
        "gpa_scale": 5.0
    }
}
```

---

## 5.1 school

類型：

`string`

必要：

是

說明：

學校名稱。

範例：

```json
"school": "Example University"
```

---

## 5.2 country

類型：

`string`

必要：

是

說明：

國家或地區資訊。

範例：

```json
"country": "Taiwan"
```

---

## 5.3 version

類型：

`string`

必要：

是

說明：

此文件所使用的 GRS 規範版本。

GRS v1 文件必須使用：

```json
"version": "1.0"
```

---

## 5.4 gpa_scale

類型：

`number`

必要：

是

說明：

學校 GPA 制度的最高 GPA 值

範例：

```json
4.0
```

或：

```json
5.0
```

---

## 5.5 description

類型：

`string` 或 `array`

必要：

否

說明：

額外描述此成績規則的資訊

---

# 6. supported_inputs

` supported_inputs ` 用於聲明此文件支援哪些輸入類型

範例：

```json
{
    "supported_inputs": {
        "numeric": true,
        "text": true,
        "letter": true,
        "special": false
    }
}
```

---

## 支援欄位

| 欄位 | 類型 | 說明 |
|-|-|-|
| numeric | boolean | 數值成績 |
| text | boolean | 文字成績 |
| letter | boolean | 字母成績 |
| special | boolean | 特殊成績 |

---

如果某種類型不被支援：

```json
"numeric": false
```

軟體應忽略對應設定。

---

# 7. Numeric 規則

`numeric` 物件用於定義數值成績如何轉換為 GPA

範例：

```json
{
    "numeric": {
        "mode": "linear",
        "min_score": 60,
        "max_score": 100,
        "min_gpa": 1.0,
        "max_gpa": 5.0
    }
}
```

---

# 7.1 mode

類型：

`string`

必要：

是

允許值：

- `range`
- `linear`
- `lookup`

說明：

定義數值成績轉換 GPA 的方式

---

# 7.2 Linear 模式

Linear 模式使用兩個基準點進行線性插值

範例：

```json
{
    "mode": "linear",
    "min_score": 60,
    "max_score": 100,
    "min_gpa": 1.0,
    "max_gpa": 5.0
}
```

代表：

```
60 分 = GPA 1.0

100 分 = GPA 5.0
```

兩者之間的分數會按照比例計算 GPA

---

# 7.3 Range 模式

Range 模式使用分數區間對應固定 GPA

範例：

```json
{
    "mode": "range",
    "rules": [
        {
            "name": "A",
            "min": 90,
            "max": 100,
            "gpa": 4.0
        }
    ]
}
```

每個規則包含：

| 欄位 | 類型 | 說明 |
|-|-|-|
| name | string | 成績名稱 |
| min | number | 最低分數 |
| max | number | 最高分數 |
| gpa | number | 對應 GPA |

---

# 7.4 Lookup 模式

Lookup 模式使用精確數值查找 GPA

範例：

```json
{
    "mode": "lookup",
    "rules": [
        {
            "score": 100,
            "gpa": 5.0
        }
    ]
}
```

---

# 8. Text 規則

`text` 物件用於文字成績與 GPA 的映射

範例：

```json
{
    "text": {
        "Excellent": 4.0,
        "優秀": 4.0,
        "良好": 3.0,
        "中等": 2.0,
        "及格": 1.0
    }
}
```

匹配規則：

- 必須完全匹配
- 區分大小寫
- 不支援自動別名
- 不支援模糊匹配

---

# 9. Letter 規則

`letter` 物件用於字母成績與 GPA 的映射

範例：

```json
{
    "letter": {
        "A+": 4.0,
        "A": 4.0,
        "B": 3.0,
        "F": 0.0
    }
}
```

支援哪些字母等級，由學校規則決定

---

# 10. Special 規則

`special` 物件用於定義特殊成績的處理方式

範例：

```json
{
    "special": {
        "P": "exclude",
        "W": "exclude"
    }
}
```

支援行為：

| 值 | 說明 |
|-|-|
| exclude | 不計入 GPA 計算 |
| zero | 以 GPA 0.0 計算 |

---

# 11. 驗證要求

有效的 GRS v1 文件必須：

- 包含 metadata
- 包含 supported_inputs
- 使用有效版本號
- 使用有效 GPA 範圍
- 使用支援的 numeric 模式
- 使用正確資料類型

無效文件不應被處理

---

# 12. 輸入匹配優先級

當多種輸入類型同時存在時，軟體應按照以下順序匹配：

1. Special 特殊成績
2. Text 文字成績
3. Letter 字母成績
4. Numeric 數值成績

第一個成功匹配的規則將被使用

---

# 13. 完整範例

```json
{
    "metadata": {
        "school": "Example University",
        "country": "Unknown",
        "version": "1.0",
        "gpa_scale": 5.0
    },

    "supported_inputs": {
        "numeric": true,
        "text": true,
        "letter": true,
        "special": false
    },

    "numeric": {
        "mode": "linear",
        "min_score": 60,
        "max_score": 100,
        "min_gpa": 1.0,
        "max_gpa": 5.0
    }
}
```

---

# 14. 未來相容性

GRS 的設計考慮未來擴展

未來版本可能加入：

- 新欄位
- 新成績制度
- 更多描述資訊

未來版本應提高版本號

例如：

```
GRS v2
```

GRS v1 文件應盡可能保持可讀性

---

# GRS v1 Specification 完
