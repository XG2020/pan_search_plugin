# 网盘搜索插件

根据关键词在慢读网盘搜索服务中检索公开分享资源，返回资源名称与下载链接。

## 功能

- 支持关键词搜索网盘资源
- 返回网盘名称、资源标题和链接
- 结果最多返回 20 条

## 安装

将插件目录放入 Nekro 插件目录，确保 `init.py` 可被加载。

## 使用

调用插件方法并传入关键词：

- 方法名：搜索网盘资源
- 参数：query（搜索关键词）

返回示例：

```
搜索关键词：xx
1. 【quark】xxxx - https://pan.quark.cn/s/xxxxxxxxx
```

## 配置

插件配置在 `PanSearchConfig` 中：

- API_URL：搜索接口地址，默认 `https://so.slowread.net/search`
- TIMEOUT：请求超时秒数，默认 20
- USER_AGENT：浏览器 UA

## 接口说明

- 请求地址：`https://so.slowread.net/search`
- 请求方式：POST
- 请求类型：`application/x-www-form-urlencoded`
- 请求参数：
  - pan_type：空字符串
  - query：搜索关键词

## 解析规则

- 网盘名称：结果卡片 `<img>` 的 `alt`
- 资源名称：结果卡片 `<h3>` 文本
- 下载链接：结果卡片 `<a>` 的 `href`

## 说明

返回结果为直接输出，不进行二次询问。未命中时返回提示语。
