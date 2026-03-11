"use strict";
/*
 * Copyright (c) 2026 Principal Systems Architect
 * This file is part of TPCP.
 *
 * TPCP is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * TPCP is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with TPCP. If not, see <https://www.gnu.org/licenses/>.
 *
 * For commercial licensing inquiries, see COMMERCIAL_LICENSE.md
 */
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.LWWMap = void 0;
const fast_json_stable_stringify_1 = __importDefault(require("fast-json-stable-stringify"));
class LWWMap {
    nodeId;
    _state = {};
    logicalClock = 0;
    constructor(nodeId) {
        this.nodeId = nodeId;
    }
    set(key, value, timestamp, writerId) {
        if (timestamp === undefined) {
            this.logicalClock += 1;
            timestamp = this.logicalClock;
            writerId = this.nodeId;
        }
        else {
            this.logicalClock = Math.max(this.logicalClock, timestamp);
            if (writerId === undefined) {
                writerId = this.nodeId;
            }
        }
        if (key in this._state) {
            const [existingValue, existingTs, existingWriter] = this._state[key];
            if (timestamp > existingTs) {
                this._state[key] = [value, timestamp, writerId];
            }
            else if (timestamp === existingTs) {
                if (writerId > existingWriter) {
                    this._state[key] = [value, timestamp, writerId];
                }
                else if (writerId === existingWriter) {
                    if ((0, fast_json_stable_stringify_1.default)(value) > (0, fast_json_stable_stringify_1.default)(existingValue)) {
                        this._state[key] = [value, timestamp, writerId];
                    }
                }
            }
        }
        else {
            this._state[key] = [value, timestamp, writerId];
        }
    }
    get(key) {
        if (key in this._state) {
            return this._state[key][0];
        }
        return null;
    }
    merge(otherState) {
        for (const [key, record] of Object.entries(otherState)) {
            this.set(key, record.value, record.timestamp, record.writer_id);
        }
    }
    toDict() {
        const result = {};
        for (const [k, v] of Object.entries(this._state)) {
            result[k] = v[0];
        }
        return result;
    }
    serializeState() {
        const result = {};
        for (const [k, [val, ts, writer]] of Object.entries(this._state)) {
            result[k] = { value: val, timestamp: ts, writer_id: writer };
        }
        return result;
    }
}
exports.LWWMap = LWWMap;
