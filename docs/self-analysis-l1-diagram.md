# The Door — L1 功能圖形（自我分析）

`mermaid
flowchart TD
    %% Confidence-based styling
    classDef high fill:#d4edda,stroke:#28a745
    classDef medium fill:#fff3cd,stroke:#ffc107,stroke-dasharray:5 5
    classDef low fill:#f8d7da,stroke:#dc3545,stroke-dasharray:2 2
    classDef reviewed fill:#cce5ff,stroke:#007bff,stroke-width:3
    classDef regenerated fill:#e8d5f5,stroke:#6f42c1,stroke-dasharray:10 5 2 5
    classDef incomplete fill:#e9ecef,stroke:#6c757d,stroke-dasharray:2 2

    feat-code-structure-extraction["✓ 程式碼結構辨識<br/><i>使用者指定一個程式碼目錄後觸發</i>"]
    class feat-code-structure-extraction high
    feat-dependency-priority-analysis["✓ 依賴優先序分析<br/><i>程式碼結構辨識完成後自動執行</i>"]
    class feat-dependency-priority-analysis high
    feat-functional-translation["✓ 功能語言翻譯<br/><i>使用者執行一鍵分析時觸發</i>"]
    class feat-functional-translation high
    feat-llm-provider-management["✓ 語言模型供應商管理<br/><i>使用者在設定檔中選擇供應商後，分析時自動使用</i>"]
    class feat-llm-provider-management high
    feat-output-quality-verification["✓ 翻譯品質驗證<br/><i>翻譯完成後自動執行</i>"]
    class feat-output-quality-verification high
    feat-visual-diagram-generation["✓ 功能圖形產出<br/><i>使用者要求產出圖形時觸發</i>"]
    class feat-visual-diagram-generation high
    feat-version-comparison["✓ 版本比對<br/><i>使用者指定兩個版本後觸發</i>"]
    class feat-version-comparison high
    feat-vulnerability-scanning["✓ 漏洞掃描<br/><i>分析程式碼時自動並行執行</i>"]
    class feat-vulnerability-scanning high
    feat-scope-verification["✓ 範圍驗核<br/><i>使用者指定範圍定義後觸發</i>"]
    class feat-scope-verification high
    feat-doubt-tracking["✓ 疑義追蹤<br/><i>使用者發現異常並建立疑義時觸發</i>"]
    class feat-doubt-tracking high
    feat-feature-evolution-timeline["✓ 功能演進時間軸<br/><i>使用者查看功能演進時觸發</i>"]
    class feat-feature-evolution-timeline high
    feat-update-pipeline["✓ 版本更新管線<br/><i>使用者指定舊版和新版目錄後觸發</i>"]
    class feat-update-pipeline high
    feat-analysis-record["✓ 分析過程記錄<br/><i>每次翻譯過程中自動記錄</i>"]
    class feat-analysis-record high

    feat-code-structure-extraction --> feat-dependency-priority-analysis
    feat-dependency-priority-analysis --> feat-functional-translation
    feat-functional-translation --> feat-output-quality-verification
    feat-output-quality-verification --> feat-visual-diagram-generation
    feat-functional-translation --> feat-analysis-record
    feat-version-comparison --> feat-scope-verification
    feat-scope-verification --> feat-doubt-tracking
    feat-update-pipeline --> feat-functional-translation
    feat-update-pipeline --> feat-version-comparison
    feat-update-pipeline --> feat-feature-evolution-timeline
    feat-code-structure-extraction --> feat-vulnerability-scanning
`
