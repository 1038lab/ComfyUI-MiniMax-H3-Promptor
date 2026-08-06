import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const SUPPORTED_NODES = new Set(["H3_Promptor", "H3_Vision_Analyzer"]);
const LOCAL_PROVIDERS = new Set(["ollama", "lmstudio"]);

const AUTO_LABELS = {
    lmstudio: "(Auto — loaded model)",
    ollama: "(Use config default)",
};

const AUTO_LABEL_VALUES = new Set(Object.values(AUTO_LABELS));

async function fetchModels(provider) {
    try {
        const response = await api.fetchApi(
            `/h3_promptor/models?provider=${encodeURIComponent(provider)}`
        );
        if (!response.ok) {
            return [];
        }
        const data = await response.json();
        return Array.isArray(data.models) ? data.models : [];
    } catch (error) {
        console.warn("[H3-Promptor] Failed to fetch models:", error);
        return [];
    }
}

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function addWidgetAt(node, index, type, name, value, options = {}) {
    const widget = node.addWidget(type, name, value, () => {}, options);
    node.widgets.pop();
    node.widgets.splice(index, 0, widget);
    return widget;
}

function attachComboSerializer(widget) {
    widget.serializeValue = () => {
        if (!widget.value || AUTO_LABEL_VALUES.has(widget.value)) {
            return "";
        }
        return widget.value;
    };
}

function buildComboValues(provider, models) {
    const autoLabel = AUTO_LABELS[provider] ?? "(Default)";
    const uniqueModels = [...new Set(models.filter(Boolean))];
    return [autoLabel, ...uniqueModels];
}

function resolveComboValue(provider, rawValue, values) {
    if (!rawValue) {
        return values[0];
    }
    if (values.includes(rawValue)) {
        return rawValue;
    }
    return values[0];
}

function setupModelSelect(node) {
    const providerWidget = findWidget(node, "provider");
    const modelWidget = findWidget(node, "model_name");
    if (!providerWidget || !modelWidget) {
        return;
    }

    let textFallbackValue = typeof modelWidget.value === "string" ? modelWidget.value : "";

    async function refreshModelWidget(provider) {
        const index = node.widgets.findIndex((widget) => widget.name === "model_name");
        if (index === -1) {
            return;
        }

        const currentWidget = node.widgets[index];
        const rawValue =
            currentWidget.type === "combo"
                ? currentWidget.serializeValue?.() ?? currentWidget.value
                : currentWidget.value ?? textFallbackValue;

        if (LOCAL_PROVIDERS.has(provider)) {
            const models = await fetchModels(provider);
            const values = buildComboValues(provider, models);
            const nextValue = resolveComboValue(provider, rawValue, values);

            if (currentWidget.type === "combo") {
                currentWidget.options.values = values;
                currentWidget.value = nextValue;
            } else {
                textFallbackValue = rawValue;
                const combo = addWidgetAt(
                    node,
                    index,
                    "combo",
                    "model_name",
                    nextValue,
                    {
                        values,
                        serialize: true,
                        tooltip: currentWidget.options?.tooltip,
                    }
                );
                attachComboSerializer(combo);
                node.widgets.splice(index + 1, 1);
            }
        } else if (currentWidget.type === "combo") {
            const restoredValue = currentWidget.serializeValue?.() ?? currentWidget.value ?? "";
            textFallbackValue = AUTO_LABEL_VALUES.has(restoredValue) ? "" : restoredValue;
            addWidgetAt(
                node,
                index,
                "text",
                "model_name",
                textFallbackValue,
                {
                    serialize: true,
                    tooltip: currentWidget.options?.tooltip,
                }
            );
            node.widgets.splice(index + 1, 1);
        } else {
            textFallbackValue = currentWidget.value ?? textFallbackValue;
        }

        node.setSize(node.computeSize());
        node.setDirtyCanvas(true, true);
    }

    const originalCallback = providerWidget.callback;
    providerWidget.callback = (value) => {
        originalCallback?.call(node, value);
        refreshModelWidget(value);
    };

    refreshModelWidget(providerWidget.value);
}

app.registerExtension({
    name: "H3Promptor.ModelSelect",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!SUPPORTED_NODES.has(nodeData.name)) {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function (...args) {
            const result = onNodeCreated?.apply(this, args);
            setupModelSelect(this);
            return result;
        };
    },
});
