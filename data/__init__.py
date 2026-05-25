"""
数据层模块。

包含：
  - loader.py          文件读取（CSV/Excel/JSON），自动检测编码
  - preprocessor.py    Pipeline 清洗（去重→文本清洗→缺失值填充→类型转换→异常标记→特征工程）
  - analyzer.py        统计分析（趋势/商品/RFM/相关/时段/国家分布）
  - detector.py        异常检测（IQR / Z-Score / 趋势突变）
  - quality_scorer.py  数据质量评分卡（5 维度加权评分，零 API 依赖）
  - profiler.py        数据画像检测（6 种模式自动识别，生成描述/建议问题/列信息）

来源：学生+AI
"""
