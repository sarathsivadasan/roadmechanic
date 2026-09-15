/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class RoadMechanicDashboard extends Component {
    static template = "odex_road_mechanic.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            stats: {},
            recent_workshops: [],
            pending_workshops: [],
            recent_reviews: [],
            recent_inquiries: [],
        });
        onWillStart(() => this.loadData());
    }

    async loadData() {
        const data = await this.orm.call(
            "odex.road.mechanic.workshop",
            "get_dashboard_data",
            []
        );
        Object.assign(this.state, data, { loading: false });
    }

    openAction(xmlId) {
        this.action.doAction(xmlId);
    }

    openRecord(model, resId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    formatDate(value) {
        if (!value) {
            return "";
        }
        return String(value).slice(0, 10);
    }
}

registry.category("actions").add("orm_road_mechanic_dashboard", RoadMechanicDashboard);
