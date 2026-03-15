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

/**
 * RelayTPCPNode — client-only TPCP node for browser, serverless, and NAT environments.
 *
 * Unlike TPCPNode, RelayTPCPNode does NOT open an inbound WebSocket server.
 * All traffic flows through the A-DNS relay connection.
 */

import { TPCPNode } from "./node";
import { AgentIdentity } from "../schemas/envelope";

export class RelayTPCPNode extends TPCPNode {
  constructor(identity: AgentIdentity, adnsUrl: string) {
    if (!adnsUrl) {
      throw new Error(
        "RelayTPCPNode requires adnsUrl — provide the URL of a running A-DNS relay server."
      );
    }
    // Pass host/port as unused placeholders; relay is the only transport
    super(identity, "127.0.0.1", 0, adnsUrl);
  }

  /**
   * Start relay-only mode: connect to the relay and begin receiving messages.
   * Does NOT start a local WebSocket server.
   */
  public async startListening(): Promise<void> {
    console.log(
      `[RelayTPCPNode] Starting in relay-only mode via ${this.adnsUrl} (no local server port)`
    );
    // Set _running so the ADNS reconnect loop stays alive
    this._running = true;
    // Start the ADNS connection loop (inherited from TPCPNode)
    this._connectToADNS();
  }
}
