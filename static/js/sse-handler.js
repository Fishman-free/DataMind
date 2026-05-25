/**
 * SSE 流式连接处理器 — DataMind v2.0
 *
 * 使用 fetch + ReadableStream 实现 POST SSE（EventSource 仅支持 GET）。
 * 提供统一的流式消息分发机制，供聊天、报告、图表等模块复用。
 *
 * 用法：
 *   const conn = createSSEConnection('/api/chat', { question: '...' }, {
 *       onTextDelta(content) { ... },
 *       onCodeComplete(code) { ... },
 *       onExecResult(result) { ... },
 *       onChart(chartData) { ... },
 *       onError(message) { ... },
 *       onDone() { ... },
 *   });
 *   // conn.abort() 取消连接
 */

/**
 * 检测浏览器是否支持 SSE（通过 ReadableStream）。
 * @returns {boolean}
 */
function supportsSSE() {
    return (
        typeof fetch !== 'undefined' &&
        typeof ReadableStream !== 'undefined' &&
        typeof TextDecoder !== 'undefined'
    );
}

/**
 * 创建 SSE 连接。
 *
 * @param {string} url - POST 端点地址
 * @param {object} body - 请求体（JSON 序列化）
 * @param {object} handlers - 事件处理器映射
 * @param {function} [handlers.onConnect] - 连接建立时调用
 * @param {function} [handlers.onTextDelta] - 收到 text_delta 事件
 * @param {function} [handlers.onCodeComplete] - 代码块传输完成
 * @param {function} [handlers.onExecResult] - 代码执行结果
 * @param {function} [handlers.onChart] - 图表数据
 * @param {function} [handlers.onAgentProgress] - Agent 进度更新
 * @param {function} [handlers.onSection] - Agent 报告章节
 * @param {function} [handlers.onReportStart] - 报告流开始
 * @param {function} [handlers.onReportDone] - 报告流完成
 * @param {function} [handlers.onError] - 错误消息
 * @param {function} [handlers.onDone] - 流结束
 * @param {function} [handlers.onProgress] - 原始进度更新（通用 handler）
 * @returns {{ abort: function }} 带 abort 方法的连接对象
 */
function createSSEConnection(url, body, handlers) {
    const controller = new AbortController();
    let fullText = '';

    fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
    })
        .then(function (response) {
            if (!response.ok) {
                // 非 2xx 状态码，尝试解析 JSON 错误
                return response.json().then(function (errData) {
                    if (handlers.onError) {
                        handlers.onError(errData.error || '请求失败：' + response.status);
                    }
                }).catch(function () {
                    if (handlers.onError) {
                        handlers.onError('请求失败：' + response.status);
                    }
                });
            }

            // 检查是否为 SSE 流
            const contentType = response.headers.get('content-type') || '';
            if (!contentType.includes('text/event-stream')) {
                // 非 SSE 响应（可能是同步模式），当作 JSON 处理
                return response.json().then(function (data) {
                    if (handlers.onDone) {
                        handlers.onDone(data);
                    }
                });
            }

            if (handlers.onConnect) {
                handlers.onConnect();
            }

            // 读取 SSE 流
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            function processChunk(text) {
                buffer += text;
                const lines = buffer.split('\n');
                // 最后一个可能是不完整的行，保留在 buffer
                buffer = lines.pop() || '';

                let currentData = '';

                for (var i = 0; i < lines.length; i++) {
                    var line = lines[i];

                    if (line.startsWith('data: ')) {
                        currentData = line.substring(6);
                    } else if (line === 'data: [DONE]') {
                        if (handlers.onDone) {
                            handlers.onDone({ fullText: fullText });
                        }
                        return;
                    }

                    if (currentData) {
                        try {
                            var msg = JSON.parse(currentData);
                            dispatch(msg, handlers);
                            // 累积文本
                            if (msg.type === 'text_delta') {
                                fullText += msg.content;
                            }
                        } catch (e) {
                            // JSON 解析失败，跳过此消息
                        }
                        currentData = '';
                    }
                }
            }

            function pump() {
                return reader.read().then(function (result) {
                    if (result.done) {
                        // 流结束但没收到 [DONE]，可能是异常
                        if (handlers.onError) {
                            handlers.onError('连接意外关闭');
                        }
                        return;
                    }
                    processChunk(decoder.decode(result.value, { stream: true }));
                    return pump();
                });
            }

            return pump();
        })
        .catch(function (err) {
            if (err.name === 'AbortError') {
                return; // 用户主动取消，静默处理
            }
            if (handlers.onError) {
                handlers.onError('网络错误：' + err.message);
            }
        });

    return {
        abort: function () {
            controller.abort();
        },
    };
}

/**
 * 内部：根据消息类型分发到对应 handler。
 * @param {object} msg - SSE 消息对象
 * @param {object} handlers - handler 映射
 */
function dispatch(msg, handlers) {
    switch (msg.type) {
        case 'text_delta':
            if (handlers.onTextDelta) handlers.onTextDelta(msg.content);
            break;
        case 'code_complete':
            if (handlers.onCodeComplete) handlers.onCodeComplete(msg.code);
            break;
        case 'exec_result':
            if (handlers.onExecResult) handlers.onExecResult(msg);
            break;
        case 'chart':
            if (handlers.onChart) handlers.onChart(msg.data);
            break;
        case 'agent_progress':
            if (handlers.onAgentProgress) handlers.onAgentProgress(msg);
            break;
        case 'section':
            if (handlers.onSection) handlers.onSection(msg);
            break;
        case 'report_start':
            if (handlers.onReportStart) handlers.onReportStart(msg);
            break;
        case 'report_done':
            if (handlers.onReportDone) handlers.onReportDone(msg);
            break;
        case 'error':
            if (handlers.onError) handlers.onError(msg.message);
            break;
        case 'done':
            if (handlers.onDone) handlers.onDone(msg);
            break;
        default:
            // 未知类型，调用通用进度 handler
            if (handlers.onProgress) handlers.onProgress(msg);
    }
}
