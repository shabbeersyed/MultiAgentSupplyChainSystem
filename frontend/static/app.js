python3 - << 'PYEOF'
with open("frontend/static/app.js", "r") as f:
    content = f.read()

# 1. Add reorder handlers before 'pong'
old = "                case 'pong':\n                    break;"
new = """                // ── Reorder Agent ──────────────────────────────────────────
                case 'reorder_assessment':
                    this.reorderResult = {
                        status: data.status,
                        days_until_stockout: data.days_until_stockout,
                        reorder_point: data.reorder_point,
                        recommended_qty: data.recommended_qty,
                        predicted_daily_usage: data.predicted_daily_usage,
                        should_order: data.should_order,
                        reason: data.reason,
                        lead_time_days: data.lead_time_days,
                    };
                    this.orchestratorText = `Reorder Agent: ${data.status} — ${data.reason}`;
                    break;

                case 'order_skipped':
                    if (this.reorderResult) { this.reorderResult.should_order = false; }
                    this.orchestratorText = 'Order blocked — stock is healthy';
                    this.isProcessing = false;
                    break;
                // ── End Reorder Agent ──────────────────────────────────────

                case 'pong':
                    break;"""
content = content.replace(old, new)

# 2. Reset reorderResult in resetUpload
old = "            this.pendingOrder = null;\n            this.orchestratorText"
new = "            this.pendingOrder = null;\n            this.reorderResult = null;\n            this.orchestratorText"
content = content.replace(old, new)

# 3. Reset reorderResult in startAnalysis
old = "            this.orderResult = null;\n            this.rawLogs = [];"
new = "            this.orderResult = null;\n            this.reorderResult = null;\n            this.rawLogs = [];"
content = content.replace(old, new)

with open("frontend/static/app.js", "w") as f:
    f.write(content)
print("✅ app.js updated")
PYEOF