import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import flushPromises from "flush-promises";
import { getLocalVue } from "tests/jest/helpers";

import { useUserStore } from "@/stores/userStore";

import QuotaMeter from "./QuotaMeter.vue";

jest.mock("@/api/schema");

let configValues = { enable_quotas: true };

jest.mock("@/composables/config", () => ({
    useConfig: jest.fn(() => ({
        config: { value: { ...configValues } },
        isConfigLoaded: true,
    })),
}));

const localVue = getLocalVue();

async function createQuotaMeterWrapper(config: any, userData: any) {
    configValues = { ...config };
    const pinia = createTestingPinia();
    const userStore = useUserStore();
    userStore.currentUser = { ...userStore.currentUser, ...userData };
    const wrapper = mount(QuotaMeter, {
        localVue,
        pinia,
    });
    await flushPromises();
    return wrapper;
}

describe("QuotaMeter.vue", () => {
    it("shows a percentage usage", async () => {
        const user = {
            total_disk_usage: 5120,
            quota_percent: 50,
            quota: "100 MB",
        };
        const config = { enable_quotas: true };
        const wrapper = await createQuotaMeterWrapper(config, user);
        expect(wrapper.find(".quota-progress > span").text()).toBe("Using 50% of 100 MB");
    });

    it("changes appearance depending on usage", async () => {
        const config = { enable_quotas: true };
        {
            const user = { quota_percent: 30 };
            const wrapper = await createQuotaMeterWrapper(config, user);
            expect(wrapper.find(".quota-progress .progress-bar").classes()).toContain("bg-success");
        }
        {
            const user = { quota_percent: 80 };
            const wrapper = await createQuotaMeterWrapper(config, user);
            expect(wrapper.find(".quota-progress .progress-bar").classes()).toContain("bg-warning");
        }
        {
            const user = { quota_percent: 95 };
            const wrapper = await createQuotaMeterWrapper(config, user);
            expect(wrapper.find(".quota-progress .progress-bar").classes()).toContain("bg-danger");
        }
    });

    it("displays tooltip", async () => {
        const config = { enable_quotas: true };
        const wrapper = await createQuotaMeterWrapper(config, {});
        expect(wrapper.attributes("title")).toContain("Storage");
    });

    it("shows total usage when there is no quota", async () => {
        {
            const user = { total_disk_usage: 7168 };
            const config = { enable_quotas: false };
            const wrapper = await createQuotaMeterWrapper(config, user);
            expect(wrapper.find("span").text()).toBe("Using 7 KB");
        }
        {
            const user = {
                total_disk_usage: 21504,
                quota: "unlimited",
            };
            const config = { enable_quotas: true };
            const wrapper = await createQuotaMeterWrapper(config, user);
            expect(wrapper.find("span").text()).toBe("Using 21 KB");
        }
    });
});
