# Google Chat App Setup Guide for Wallbox SDO Platform

## 1. Google Workspace Marketplace SDK Configuration

1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/) for project **`managed-agent-504409`**.
2. Enable the **Google Chat API**.
3. Open **Google Chat API > Configuration**:
   - **App Name:** `Wallbox SDO Delivery Bot`
   - **Avatar URL:** `https://fonts.gstatic.com/s/i/short-term/release/googlegsymbol/auto_awesome/default/48px.svg`
   - **Description:** `Automated Software & Data Delivery Bot for Finance, Sales, Firmware, Marketing, and Logistics.`
   - **Functionality:** Receive 1:1 messages and Join spaces.
   - **Connection Settings:** Select `HTTP endpoint`.
   - **HTTP Endpoint URL:** `https://<YOUR_CLOUD_RUN_URL>/api/v1/chat/webhook`
   - **Authentication Audience:** `sdo-control-plane`

---

## 2. Testing Google Chat Interactions

1. Open **Google Chat** with your Wallbox Google Workspace account.
2. Start a direct message with `@Wallbox SDO Delivery Bot`.
3. Type:
   ```
   Create a weekly currency variance analysis view in BigQuery comparing EUR invoices with USD receipts.
   ```
4. The bot responds with the **Gate H1 Interactive Card** containing the generated Gherkin specification and `[Approve Specification]` button.
5. Click **Approve Specification**: The bot runs architectural design, executes tests in the sandbox, opens the GitHub PR, and sends the **Gate H2 Card** with `[Approve Merge & Deploy]`.
