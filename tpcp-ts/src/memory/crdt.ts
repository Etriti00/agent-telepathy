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

import stringify from 'fast-json-stable-stringify';

export class LWWMap {
  public nodeId: string;
  private _state: Record<string, [any, number, string]> = {};
  public logicalClock: number = 0;

  constructor(nodeId: string) {
    this.nodeId = nodeId;
  }

  public set(key: string, value: any, timestamp?: number, writerId?: string): void {
    if (timestamp === undefined) {
      this.logicalClock += 1;
      timestamp = this.logicalClock;
      writerId = this.nodeId;
    } else {
      this.logicalClock = Math.max(this.logicalClock, timestamp);
      if (writerId === undefined) {
        writerId = this.nodeId;
      }
    }

    if (key in this._state) {
      const [existingValue, existingTs, existingWriter] = this._state[key];
      
      if (timestamp > existingTs) {
        this._state[key] = [value, timestamp, writerId];
      } else if (timestamp === existingTs) {
        if (writerId > existingWriter) {
          this._state[key] = [value, timestamp, writerId];
        } else if (writerId === existingWriter) {
          if (stringify(value) > stringify(existingValue)) {
            this._state[key] = [value, timestamp, writerId];
          }
        }
      }
    } else {
      this._state[key] = [value, timestamp, writerId];
    }
  }

  public get(key: string): any {
    if (key in this._state) {
      return this._state[key][0];
    }
    return null;
  }

  public merge(otherState: Record<string, { value: any; timestamp: number; writer_id: string }>): void {
    for (const [key, record] of Object.entries(otherState)) {
      this.set(key, record.value, record.timestamp, record.writer_id);
    }
  }

  public toDict(): Record<string, any> {
    const result: Record<string, any> = {};
    for (const [k, v] of Object.entries(this._state)) {
      result[k] = v[0];
    }
    return result;
  }

  public serializeState(): Record<string, { value: any; timestamp: number; writer_id: string }> {
    const result: Record<string, { value: any; timestamp: number; writer_id: string }> = {};
    for (const [k, [val, ts, writer]] of Object.entries(this._state)) {
      result[k] = { value: val, timestamp: ts, writer_id: writer };
    }
    return result;
  }
}
