export const state = {
    toolById: {},
    toolsList: [],
    totalToolCount: undefined,
    hasHelp: true,
};

import Vue from "vue";
import { getAppRoot } from "onload/loadConfig";
import axios from "axios";

const getters = {
    getToolForId: (state) => (toolId) => {
        return state.toolById[toolId];
    },
    getToolNameById: (state) => (toolId) => {
        const details = state.toolById[toolId];
        if (details && details.name) {
            return details.name;
        } else {
            return "...";
        }
    },
    getTools:
        (state) =>
        ({ filterSettings }) => {
            // if no filters
            if (Object.keys(filterSettings).length == 0 || filterSettings == {}) {
                return [];
            }
            const allTools = state.toolsList[0];
            const returnedTools = [];

            for (const tool in allTools) {
                let hasMatches = false;
                for (const [key, filterValue] of Object.entries(filterSettings)) {
                    const actualValue = allTools[tool][key];
                    if (filterValue) {
                        if (!actualValue || !actualValue.toUpperCase().match(filterValue.toUpperCase())) {
                            hasMatches = false;
                            break;
                        } else {
                            hasMatches = true;
                        }
                    }
                }
                if (hasMatches) {
                    returnedTools.push(allTools[tool]);
                }
            }

            return returnedTools;
        },
    getTotalToolCount: (state) => () => state.totalToolCount,
};

const actions = {
    fetchToolForId: async ({ commit }, toolId) => {
        console.log("fetching tool");
        const { data } = await axios.get(`${getAppRoot()}api/tools/${toolId}`);
        commit("saveToolForId", { toolId, toolData: data });
    },
    fetchAllTools: async ({ state, commit }, { showHelp }) => {
        // Preventing store from being populated for every search: we fetch again only if:
        // store isn't already populated (initial fetch) OR user now wants (or doesn't want) help text
        if (!state.toolsList[0] || !state.totalToolCount || state.hasHelp !== showHelp) {
            console.log("fetching all tools once");
            const { data } = await axios.get(`${getAppRoot()}api/tools?tool_help=${showHelp}&in_panel=False`);
            const toolCount = data.length;
            commit("saveTotalToolCount", { toolCount });
            commit("saveShowHelp", { showHelp });
            commit("saveTools", { toolsData: data });
        }
    },
};

const mutations = {
    saveToolForId: (state, { toolId, toolData }) => {
        Vue.set(state.toolById, toolId, toolData);
    },
    saveTools: (state, { toolsData }) => {
        Vue.set(state.toolsList, 0, toolsData);
    },
    saveTotalToolCount: (state, { toolCount }) => {
        state.totalToolCount = toolCount;
    },
    saveShowHelp: (state, { showHelp }) => {
        state.hasHelp = showHelp;
    },
};

export const toolStore = {
    state,
    getters,
    actions,
    mutations,
};
