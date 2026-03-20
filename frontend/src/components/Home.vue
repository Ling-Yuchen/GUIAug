<script>
import apiClient from "../api.js";
import {
  NButton,
  NDropdown,
  NImage,
  NInput,
  // NP,
  NPopconfirm,
  NSelect,
  NSpace,
  NModal,
  NCheckbox,
} from "naive-ui";
// import JMuxer from "jmuxer";

export default {
  // eslint-disable-next-line vue/multi-word-component-names
  name: "home",
  components: {
    NImage,
    NButton,
    // NP,
    NDropdown,
    NInput,
    NPopconfirm,
    NSelect,
    NSpace,
    NModal,
    NCheckbox,
  },
  data: () => ({
    devOptions: [],
    devList: [],
    emptyDev: {
      platform: undefined,
      serialNo: undefined,
      width: undefined,
      height: undefined,
      busy: undefined,
    },
    dev: {
      platform: undefined,
      serialNo: undefined,
      width: undefined,
      height: undefined,
      busy: undefined,
    },
    scriptOptions: [],
    screenCap: {
      ws: undefined,  // The websocket to get screenshots.
      url: "",  // The url to load screenshots used by <img/>.
      state_record_url: "",
      jmuxer: undefined,  // jmuxer video player
      cursor: "default",
      cursor2: "default",
      height: 768,
      width: 480,
      bgColor: "#000000",
      mouseState: "up",
    },

    record: {
      status: "NONE",  // NONE, READY, RECORDING, PAUSED, SAVED, RUNNING
      busy: false,  // true if undergoing recording an operation
      editing: false,  // true if inserting operations into a saved script
      scriptID: "",
      scriptName: "hello",
      tempScriptName: "",
      scriptNameEditing: false,
      deviceID: "",
      description: "",
      tempDescription: "",
      descriptionEditing: false,
      prevOpID: "None",
      nextOpID: "None",
      nextOpIdx: -1,
      needInput: false,
      inputText: "",
      needOracle: false,
      oracleText: "",
      oracleImage: {
        x1: 0, y1: 0,
        x2: 0, y2: 0,
      },
      opList: [],
      perf_ready: false,
      mutating: false,
      mutate_master: "",
      migrate_master:""
    },
    replay: {
      use_perf: false,
    },
    opUpdate: {
      ws: undefined,
    },

    operationParams: {
      startX: undefined,
      startY: undefined,
      endX: undefined,
      endY: undefined,
      startTime: undefined,
      endTime: undefined,
      SCROLL_THRESHOLD: 10,
      LONG_PRESS_THRESHOLD: 500,
    },

    mutateOptions: [
        {label: "NONE", value: "NONE"},
        {label: "INPUT-DATA", value: "INPUT-DATA"},
        {label: "NON-INPUT-DATA", value: "NON-INPUT-DATA"},
        {label: "PATH", value: "PATH"},
    ],
    showModal: {
      for_input_data_mutate: false,
      for_path_mutate: false,
    },
    tempInputTextList: [],
    tempOptionContext: {
      screenWithBbox: "",
      bboxInfo: {},
      optionWidgetIds: [],
    },
    tempPathContext: {
      screenWithBbox: "",
      bboxInfo: {},
      newOperationInfo: [],
    }
  }),
  computed: {},
  watch: {
    "record.needInput": function (newVal, oldVal) {
      if (newVal === true) {
        console.log(`record.needInput changed from ${oldVal} to ${newVal}`);
        let triggerInput = document.getElementById("triggerInput");
        triggerInput.click();
      }
    },
  },
  methods: {
    connect_android() {
      this.screenCap.ws = new WebSocket("ws://localhost:8000/ws");
      let ws = this.screenCap.ws;
      ws.binaryType = "blob"; // 设置为接收二进制数据
      ws.onmessage = (msg) => {
        const anyBuffer = msg.data;
        const blob = new Blob([anyBuffer]);
        this.screenCap.url = URL.createObjectURL(blob);
      }
      ws.onopen = () => {
        ws.send(`device://${this.dev.serialNo}`);
      }
      ws.onclose = () => {
        console.log("WebSocket closed.");
      }
    },
    disconnect_android() {
      this.screenCap.ws.close();
      this.screenCap.ws = undefined;
      this.screenCap.url = "";
    },
    updateDeviceConnection() {
      if (this.screenCap.ws === undefined) {
        this.connect_android();
      } else {
        this.disconnect_android();
      }
    },
    async getDevices() {
      this.devList = [];
      this.devOptions = [];
      const response = await apiClient.get("/device/list");
      console.log(response);

      if (response.status !== 200) {
        console.log(`Fail to get devices. Response Status: ${response.status}`);
        return;
      }

      for (const device of response.data) {
        this.devList.push({
          platform: device["platform"],
          serialNo: device["serial_no"],
          width: device["width"],
          height: device["height"],
          busy: device["busy"],
        })
        console.log(this.devList);
        this.devOptions.push({
          label: device["serial_no"],
          value: device["serial_no"],
          key: device["serial_no"],
        })
      }
      if (this.devList.length === 0) {
        this.dev = this.emptyDev;
        console.log("Warning: no devices available");
      }
    },
    updateDevice(value) {
      for (const device of this.devList) {
        if (device.serialNo === value) {
          console.log(`update device ${value}`);
          this.dev.serialNo = value;
          this.dev.height = device.height;
          this.dev.width = device.width;
          this.dev.platform = device.platform;
          this.dev.busy = false;
          this.screenCap.width = Math.round(this.dev.width * 2 / 5);
          this.screenCap.height = Math.round(this.dev.height * 2 / 5);
          break
        }
      }
    },
    async updateScriptOptions(force) {
      if (this.scriptOptions.length > 0 && !force) return;

      this.scriptOptions = [];
      const response = await apiClient.get("/record/scripts");

      if (response.status !== 200) {
        console.log(`Fail to get scripts. Response Status: ${response.status}`);
        return;
      }

      for (const script of response.data) {
        this.scriptOptions.push({
          label: script.name,
          key: script.id,
        })
      }
    },

    doMouseDown(event) {
      if (this.screenCap.ws === undefined) return;
      if (this.dev.busy) return;

      this.screenCap.mouseState = "down";
      let screen = document.getElementById("screenCap");
      const x_local = event.clientX - screen.getBoundingClientRect().x;
      const y_local = event.clientY - screen.getBoundingClientRect().y;
      const x_remote = Math.round(x_local * this.dev.width / screen.getBoundingClientRect().width);
      const y_remote = Math.round(y_local * this.dev.height / screen.getBoundingClientRect().height);
      this.operationParams.startX = x_remote;
      this.operationParams.startY = y_remote;
      this.operationParams.startTime = Date.now();
      // this.screenCap.ws.send(`{"event": "down", "x": ${x_remote}, "y": ${y_remote}}`);
    },
    doMouseMove(event) {
      if (this.screenCap.ws === undefined) return;
      if (this.screenCap.mouseState !== "down") return;
      if (this.dev.busy) return;

      let screen = document.getElementById("screenCap");
      const x_local = event.clientX - screen.getBoundingClientRect().x;
      const y_local = event.clientY - screen.getBoundingClientRect().y;
      const x_remote = Math.round(x_local * this.dev.width / screen.getBoundingClientRect().width);
      const y_remote = Math.round(y_local * this.dev.height / screen.getBoundingClientRect().height);
      // this.screenCap.ws.send(`{"event": "move", "x": ${x_remote}, "y": ${y_remote}}`);
      console.log(`move: ${Date.now()}, ${x_remote}, ${y_remote}`);
    },
    async doMouseUp(event) {
      if (this.screenCap.ws === undefined) return;
      if (this.screenCap.mouseState !== "down") return;
      if (this.dev.busy) return;

      this.screenCap.mouseState = "up";
      let screen = document.getElementById("screenCap");
      const x_local = event.clientX - screen.getBoundingClientRect().x;
      const y_local = event.clientY - screen.getBoundingClientRect().y;
      const x_remote = Math.round(x_local * this.dev.width / screen.getBoundingClientRect().width);
      const y_remote = Math.round(y_local * this.dev.height / screen.getBoundingClientRect().height);
      this.operationParams.endX = x_remote;
      this.operationParams.endY = y_remote;
      this.operationParams.endTime = Date.now();
      // this.screenCap.ws.send(`{"event": "up", "x": ${x_remote}, "y": ${y_remote}}`);

      this.dev.busy = true;
      const duration = this.operationParams.endTime - this.operationParams.startTime;
      const distance = Math.sqrt(
          Math.pow(this.operationParams.endX - this.operationParams.startX, 2)
          + Math.pow(this.operationParams.endY - this.operationParams.startY, 2)
      );
      if (distance > this.operationParams.SCROLL_THRESHOLD) {
        await this.doScreenScrolled();
      } else if (duration > this.operationParams.LONG_PRESS_THRESHOLD) {
        await this.doScreenLongPressed();
      } else {
        await this.doScreenClicked();
      }
      this.dev.busy = false;

      if (this.record.status === "RECORDING") {
        if (!this.record.editing) {
          if (this.record.nextOpID !== "None" && this.record.prevOpID !== "None") {
            throw new Error("wrong editing state");
          }
        }
        this.dev.busy = true;
        // const duration = this.operationParams.endTime - this.operationParams.startTime;
        // const distance = Math.sqrt(
        //   Math.pow(this.operationParams.endX - this.operationParams.startX, 2)
        //   + Math.pow(this.operationParams.endY - this.operationParams.startY, 2)
        // );
        if (distance > this.operationParams.SCROLL_THRESHOLD) {
          await this.recordScroll();
        } else if (duration > this.operationParams.LONG_PRESS_THRESHOLD) {
          await this.recordLongPress();
        } else {
          await this.recordTap();
        }
        await this.dumpAppState(true);
        this.dev.busy = false;
      }
    },
    async doScreenClicked() {
      const device_sn = this.dev.serialNo;
      const x_remote = Math.round((this.operationParams.endX + this.operationParams.startX) / 2);
      const y_remote = Math.round((this.operationParams.endY + this.operationParams.startY) / 2);
      let request_url = `/device/tap/${device_sn}/${x_remote}/${y_remote}`;
      const response = await apiClient.get(request_url);
      console.log(response);
    },
    async doScreenScrolled() {
      const x1 = this.operationParams.startX;
      const y1 = this.operationParams.startY;
      const x2 = this.operationParams.endX;
      const y2 = this.operationParams.endY;
      const device_sn = this.dev.serialNo;
      // const duration = this.operationParams.endTime - this.operationParams.startTime;
      let request_url = `/device/scroll/${device_sn}/${x1}/${y1}/${x2}/${y2}`;
      const response = await apiClient.get(request_url);
      console.log(response);
    },
    async doScreenLongPressed() {
      const device_sn = this.dev.serialNo;
      const x_remote = Math.round((this.operationParams.endX + this.operationParams.startX) / 2);
      const y_remote = Math.round((this.operationParams.endY + this.operationParams.startY) / 2);
      let request_url = `/device/long_press/${device_sn}/${x_remote}/${y_remote}`;
      const response = await apiClient.get(request_url);
      console.log(response);
    },
    async doEnterText() {
      if (this.record.needInput) {
        let request_url = `/device/tap_input/${this.dev.serialNo}/10/10/${this.record.inputText}`;
        const response = await apiClient.get(request_url);
        console.log(response);
        if (this.record.status === "RECORDING") {
          if (!this.record.editing) {
            if (this.record.nextOpID !== "None" && this.record.prevOpID !== "None") {
              throw new Error("wrong editing state");
            }
          }
          this.dev.busy = true;
          await this.recordInput();
          await this.dumpAppState(true);
          this.dev.busy = false;
        }
        this.record.inputText = "";
        this.record.needInput = false;
      }
    },
    async doCreateAssert() {
      if (this.record.status === "RECORDING") {
        this.dev.busy = true;
        if (!this.record.editing) {
          if (this.record.nextOpID !== "None" && this.record.prevOpID !== "None") {
            throw new Error("wrong editing state");
          }
        }
        let assertParams = {};
        assertParams["text"] = this.record.oracleText;
        this.record.oracleText = "";
        let script_id = this.record.scriptID;
        let device_sn = this.dev.serialNo;
        const paramsStr = encodeURIComponent(JSON.stringify(assertParams));
        let request_url = `/record/oracle/${script_id}/${device_sn}/` +
                          `${this.record.prevOpID}/${this.record.nextOpID}?params=${paramsStr}`;
        const response = await apiClient.get(request_url);
        let opDict = response.data;
        this.handleRecordedResult(opDict);
        await this.dumpAppState(false);
        this.dev.busy = false;
      }
    },

    async recordingSwitch() {
      if (this.record.status === "READY") {
        this.record.status = "RECORDING";
        this.record.busy = true;
        await this.dumpAppState(false);
        this.record.busy = false;
      } else if (this.record.status === "RECORDING") {
        this.record.status = "READY";
        this.record.editing = false;
        this.record.prevOpID = "None";
        this.record.nextOpID = "None";
        this.record.nextOpIdx = -1;
      } else {
        console.log("no script for recording");
      }
    },
    async recordingInit() {
      if (this.record.status === "RUNNING") {
        console.log("cannot create new script when running a script");
        return;
      }
      if (this.record.status === "RECORDING") {
        console.log(`script ${this.record.scriptID} still recording`);
        return;
      }

      this.record.status = "READY";
      this.record.editing = false;
      this.record.opList = [];

      let request_url = `/record/script/new_script/${this.dev.serialNo}/undefined`;
      const response = await apiClient.get(request_url);
      const script = response.data;
      this.record.scriptID = script.script_id;
      this.record.deviceID = script.device_id;
      this.record.scriptName = script.script_name;
      this.record.description = script.description;
      this.record.perf_ready = script.perf_ready;
      await this.updateScriptOptions(true);
    },
    async scriptDiscard() {
      if (this.record.status === "NONE") {
        console.log("no script to discard");
        return;
      }
      if (this.record.status === "RUNNING") {
        console.log("cannot discard a running script");
        return;
      }

      let request_url = `/record/discard/${this.record.scriptID}`;
      const response = await apiClient.get(request_url);
      console.log(response);

      this.record.scriptID = undefined;
      this.record.opList = [];
      this.record.status = "NONE";
      await this.updateScriptOptions(true);
    },
    async removeOperation(opIdx) {
      if (this.record.status === "RUNNING") {
        console.log("cannot remove operation when running a script");
        return;
      }
      if (this.record.status === "NONE") { return; }
      let opToDel = this.record.opList[opIdx];
      let request_url = `/record/remove_operation/${this.record.scriptID}/${opToDel.op_id}`;
      const response = await apiClient.get(request_url);
      console.log(response);
      this.record.opList.splice(opIdx, 1);
      this.record.perf_ready = false;
    },
    async insertOperation(opIdx) {
      if (this.record.status === "RUNNING") {
        console.log("cannot insert operations into a running script");
        return;
      }
      if (this.record.status !== "READY") {
        console.log("cannot insert operations into a recording script");
        return;
      }
      this.record.status = "RECORDING";
      this.record.editing = true;
      if (opIdx >= 0) {
        this.record.prevOpID = this.record.opList[opIdx].op_id;
      } else {
        this.record.prevOpID = "None";
      }
      if (opIdx + 1 < this.record.opList.length) {
        this.record.nextOpID = this.record.opList[opIdx + 1].op_id;
        this.record.nextOpIdx = opIdx + 1;
      } else {
        this.record.nextOpID = "None";
        this.record.nextOpIdx = opIdx + 1;
      }
      await this.dumpAppState(false);
    },
    async editOperation(opIdx) {
      this.record.opList[opIdx].edit_enable = !this.record.opList[opIdx].edit_enable;
      if (this.record.opList[opIdx].edit_enable) {
        this.record.opList[opIdx].edit_btn_txt = "完成";
      } else {
        this.record.opList[opIdx].edit_btn_txt = "编辑";
        let params = {"params": this.record.opList[opIdx].op_params}
        const paramsStr = encodeURIComponent(JSON.stringify(params));
        const request_url = `/record/update_params/${this.record.scriptID}/`
          + `${this.record.opList[opIdx].op_id}?params=${paramsStr}`;
        await apiClient.get(request_url);
        this.record.perf_ready = false;
      }
    },
    async dumpAppState(wait) {
      let request_url = `/record/dump/${this.dev.serialNo}/${wait}`;
      let response = await apiClient.get(request_url);
      this.screenCap.state_record_url = `data:image/jpeg;base64,${response.data}`;
    },

    async recordTap() {
      const script_id = this.record.scriptID;
      const device_sn = this.dev.serialNo;
      const x_remote = Math.round((this.operationParams.endX + this.operationParams.startX) / 2);
      const y_remote = Math.round((this.operationParams.endY + this.operationParams.startY) / 2);
      let request_url = `/record/tap/${script_id}/${x_remote}/${y_remote}/`+
                `${device_sn}/${this.record.prevOpID}/${this.record.nextOpID}`;
      const response = await apiClient.get(request_url);
      let opDict = response.data;
      this.handleRecordedResult(opDict);
    },
    async recordLongPress() {
      const script_id = this.record.scriptID;
      const device_sn = this.dev.serialNo;
      const x_remote = Math.round((this.operationParams.endX + this.operationParams.startX) / 2);
      const y_remote = Math.round((this.operationParams.endY + this.operationParams.startY) / 2);
      let request_url = `/record/long_press/${script_id}/${x_remote}/${y_remote}/`+
                        `${device_sn}/${this.record.prevOpID}/${this.record.nextOpID}`;
      const response = await apiClient.get(request_url);
      let opDict = response.data;
      this.handleRecordedResult(opDict);
    },
    async recordScroll() {
      const x1 = this.operationParams.startX;
      const y1 = this.operationParams.startY;
      const x2 = this.operationParams.endX;
      const y2 = this.operationParams.endY;
      const script_id = this.record.scriptID;
      const device_sn = this.dev.serialNo;
      const duration = this.operationParams.endTime - this.operationParams.startTime;
      let request_url = `/record/scroll/${script_id}/${x1}/${y1}/${x2}/${y2}/` +
                        `${device_sn}/${duration}/${this.record.prevOpID}/${this.record.nextOpID}`;
      const response = await apiClient.get(request_url);
      let opDict = response.data;
      this.handleRecordedResult(opDict);
    },
    async recordInput() {
      const script_id = this.record.scriptID;
      const device_sn = this.dev.serialNo;
      let request_url = `/record/tap_input/${script_id}/10/10/${this.record.inputText}/` +
                        `${device_sn}/${this.record.prevOpID}/${this.record.nextOpID}`;
      const response = await apiClient.get(request_url);
      let opDict = response.data;
      this.handleRecordedResult(opDict);
    },

    handleRecordedResult(opDict) {
      this.record.needInput = opDict.require_input;
      console.log(this.record.needInput);
      if (opDict.widget_img.length > 0) {
        opDict.widget_img = `data:image/jpeg;base64,${opDict.widget_img}`;
      }
      opDict["checked"] = false;
      opDict["edit_enable"] = false;
      opDict["edit_btn_txt"] = "编辑";
      opDict["replay"] = undefined;
      if (opDict.widget_desc && opDict.widget_desc.length > 20) {
        opDict.widget_desc = opDict.widget_desc.substring(0, 20) + "...";
      }
      if (this.record.nextOpID === "None") {
        this.record.opList.push(opDict);
      } else if (this.record.prevOpID === "None") {
        this.record.opList.unshift(opDict);
        this.record.prevOpID = this.record.opList[0].op_id;
        this.record.nextOpIdx += 1;
      } else {
        this.record.opList.splice(this.record.nextOpIdx, 0, opDict);
        this.record.prevOpID = opDict.op_id;
        this.record.nextOpIdx += 1;
      }
    },

    onMouseEnterScreenCap() {
      if (!this.dev.busy) {
        this.screenCap.cursor = "pointer";
      } else {
        this.screenCap.cursor = "wait";
      }
    },
    onMouseLeaveScreenCap() {
      this.screenCap.cursor = "default";
      this.screenCap.mouseState = "up";
    },
    onMouseEnterScreenshot() { this.screenCap.cursor2 = "pointer"; },
    onMouseLeaveScreenshot() { this.screenCap.cursor2 = "default"; },

    async handleScriptSelect(key) {
      let request_url = `/record/script_op_list/${key}`;
      const response = await apiClient.get(request_url);
      let script = response.data;
      let operationList = script.operations;
      console.log(operationList);

      this.record.opList = [];
      for (const item of operationList) {
        let op = item;
          if (op.widget_img.length > 0) {
            op["widget_img"] = `data:image/jpeg;base64,${op.widget_img}`;
          }
          op["checked"] = false;
          op["edit_enable"] = false;
          op["edit_btn_txt"] = "编辑";
          op["replay"] = undefined;
          if (op.widget_desc.length > 40) {
            op.widget_desc = op.widget_desc.substring(0, 40) + "...";
          }
          this.record.opList.push(op);
      }

      this.record.scriptID = String(key);
      this.record.status = "READY";
      this.record.scriptName = script.script_name;
      this.record.description = script.description;
      this.record.deviceID = script.device_id;
      this.record.mutating = script.mutating;
      this.record.mutate_master = script.mutate_master;
    },
    async replayScript() {
      await this.handleScriptSelect(this.record.scriptID);
      let replay_success = true;
      let fail_count = 0;
      for (let i = 0; i < this.record.opList.length; i++) {
        const op = this.record.opList[i];
        const response = await this.replayOperation(op);
        this.record.opList[i].replay = true;
        if (response.status !== 200 || response.data.includes("failed")) {
          console.log("replay failed");
          this.record.opList[i].replay = false;
          fail_count += 1;
          // if (fail_count > 1) { replay_success = false; }
          // if (!replay_success) { break; }
        } else {
          fail_count = 0;
        }
      }
      if (fail_count > 0 && replay_success) { replay_success = false; }
      this.$message.info(`ScriptID ${this.record.scriptID} replay result: ${replay_success}`)
    },
    async replayOperation(op) {
      const opStr = encodeURIComponent(JSON.stringify(op));
      let request_url = `/record/replay/${this.record.scriptID}/${this.dev.serialNo}?op_str=${opStr}`;
      return await apiClient.get(request_url);
    },
    async generateScriptDescription() {
      let request_url = `/record/generate_intent/${this.record.scriptID}`;
      await apiClient.get(request_url);
      await this.handleScriptSelect(this.record.scriptID);
    },
    async prepare_for_mutation() {
      if (this.record.status !== "READY") {
        this.$message.warning("no script");
      } else {
        let request_url = `/mutate/prepare/${this.record.scriptID}`;
        const response = await apiClient.get(request_url);
        this.$message.info(response.data);
        // this.record.mutate_state.model = response.data;
        await this.handleScriptSelect(this.record.scriptID);
        // console.log(this.record.opList);
      }
    },

    async editScriptName() {
      if (this.record.status !== "READY") return;
      if (this.record.scriptNameEditing) {
        let request_url = `/record/update_name/${this.record.tempScriptName}/${this.record.scriptID}`;
        await apiClient.get(request_url);
        this.record.scriptName = this.record.tempScriptName;
        this.record.perf_ready = false;
        await this.updateScriptOptions(true);
      } else {
        this.record.tempScriptName = this.record.scriptName;
      }
      this.record.scriptNameEditing = !this.record.scriptNameEditing;
    },
    async editScriptDesc() {
      if (this.record.status !== "READY") return;
      if (this.record.descriptionEditing) {
        let request_url = `/record/update_desc/${this.record.tempDescription}/${this.record.scriptID}`;
        await apiClient.get(request_url);
        this.record.description = this.record.tempDescription;
        this.record.perf_ready = false;
        await this.updateScriptOptions(true);
      } else {
        this.record.tempDescription = this.record.description;
      }
      this.record.descriptionEditing = !this.record.descriptionEditing;
    },

    async updateMutateType(opIdx) {
      let op = this.record.opList[opIdx];
      let mutate_type = op.mutate_type;
      let request_url = `/mutate/update_mutate/${this.record.scriptID}/${op.op_id}/${mutate_type}`;
      await apiClient.get(request_url);
      await this.handleScriptSelect(this.record.scriptID);
    },
    async doInputDataMutate() {
      let op_id = ""
      for (let i = 0; i < this.record.opList.length; i++) {
        const op = this.record.opList[i];
        if (op["checked"]) {
          op_id = op["op_id"];
          break;
        }
      }
      if (op_id !== "") {
        const request_url = `/mutate/input_data/${this.record.scriptID}/${op_id}`;
        const response = await apiClient.get(request_url);
        this.tempInputTextList = response.data;
      } else {
        this.$message.warning("没有选择变异点")
        this.showModal.for_input_data_mutate = false;
      }
    },
    async doPathMutate() {},
    onInputDataMutateCancel() {
      this.showModal.for_input_data_mutate = false;
      this.tempInputTextList = [];
    },
    onPathMutateCancel() {
      this.showModal.for_path_mutate = false;
      this.tempPathContext.screenWithBbox = "";
      this.tempPathContext.bboxInfo = {};
      this.tempPathContext.newOperationInfo = [];
    },
    async onInputDataMutateConfirm() {
      let op_id = ""
      for (let i = 0; i < this.record.opList.length; i++) {
        const op = this.record.opList[i];
        if (op["checked"]) {
          op_id = op["op_id"];
          break;
        }
      }
      if (op_id !== "") {
        let request_url = `/mutate/input_data_confirm/${this.record.scriptID}/${op_id}`;
        // let new_data = `?`;
        // for (let i = 0; i < this.tempInputTextList.length; ++i) {
        //   let text = this.tempInputTextList[i][0];
        //   new_data += `new_data=${text}`
        //   if (i < this.tempInputTextList.length - 1) {
        //     new_data += "&"
        //   }
        // }
        // request_url += new_data;
        console.log(this.tempInputTextList);
        let request_body = {"data": this.tempInputTextList};
        const response = await apiClient.post(request_url, request_body);
        // const response = await apiClient.get(request_url);
        this.$message.info(response.data);
        await this.updateScriptOptions(true);
      }
      this.showModal.for_input_data_mutate = false;
    },
    async onPathMutateConfirm() {
      let op_id = ""
      for (let i = 0; i < this.record.opList.length; i++) {
        const op = this.record.opList[i];
        if (op["checked"]) {
          op_id = op["op_id"];
          break;
        }
      }
      if (op_id !== "") {
        let request_url = `/mutate/path_confirm/${this.record.scriptID}/${op_id}`;
        let request_body = {
          "bbox": this.tempPathContext.bboxInfo,
          "feasible_choices": this.tempPathContext.newOperationInfo,
        }
        const response = await apiClient.post(request_url, request_body);
        this.$message.info(response.data);
        await this.updateScriptOptions(true);
      }
      this.showModal.for_path_mutate = false;
    },
    async completeMutatingScript() {
      let request_url = `/mutate/path_complete/${this.record.scriptID}/${this.dev.serialNo}`;
      const response = await apiClient.get(request_url);
      this.$message.info(response.data);
      await this.handleScriptSelect(this.record.scriptID);
      // if (this.record.mutating) {
      //   let request_url = `/mutate/path_complete/${this.record.scriptID}/${this.dev.serialNo}`;
      //   const response = await apiClient.get(request_url);
      //   this.$message.info(response.data);
      //   await this.handleScriptSelect(this.record.scriptID);
      // } else {
      //   this.$message.warning("当前脚本mutating属性为false!");
      // }
    },
  },
}
</script>

<template>
<div class="container">

  <div style="width: 400px; height: 700px">
    <n-image
      id="screenshot"
      v-if="this.screenCap.state_record_url"
      :src="this.screenCap.state_record_url"
      :preview-disabled="true"
      @click="dumpAppState(false)"
      @mouseenter="onMouseEnterScreenshot"
      @mouseleave="onMouseLeaveScreenshot"
      :style="{cursor: this.screenCap.cursor2}"/>
  </div>

  <div class="deviceContainer">
    <div class="screenContainer" :style="`background-color: ${this.screenCap.bgColor}; height: 1024px; width: 640px`">
      <n-image v-if="screenCap.url"
        id="screenCap"
        :src="screenCap.url"
        :style="{cursor: this.screenCap.cursor}"
        @mouseenter="onMouseEnterScreenCap"
        @mouseleave="onMouseLeaveScreenCap"
        @mousedown="doMouseDown"
        @mousemove="doMouseMove"
        @mouseup="doMouseUp"
        :preview-disabled="true"
        @contextmenu.prevent="true"
        alt="screenCap"/>
    </div>
  </div>

  <div class="scriptInfoContainer" style="width: 400px; border: 2px #000000 solid">
    <div style="margin-bottom: 20px">ScriptID: {{ this.record.scriptID }}</div>
    <div style="margin-bottom: 20px">Device: {{ this.record.deviceID }}</div>
    <div style="margin-bottom: 20px">State: {{ this.record.status }}</div>
    <div style="margin-bottom: 20px">PerfReady: {{ this.record.perf_ready }}</div>
    <div style="margin-bottom: 20px">Mutating: {{ this.record.mutating }}</div>
    <div style="margin-bottom: 20px">Mutate_Master: {{ this.record.mutate_master }}</div>
    <div style="margin-bottom: 20px">Migrate_Master: {{ this.record.migrate_master }}</div>
    <div style="margin-bottom: 20px">
      <span>
        <span>Name:</span>
        <n-input
          v-if="this.record.scriptNameEditing"
          v-model:value="this.record.tempScriptName"
          size="small" style="width: 100px"
        />
        <span v-else>{{ this.record.scriptName }}</span>
      </span>
      <n-button size="small" @click="this.editScriptName">{{ this.record.scriptNameEditing ? '保存' : '编辑' }}</n-button>
    </div>
    <div style="margin-bottom: 20px">
      <span>
        <span>Description:</span>
        <n-input
          v-if="this.record.descriptionEditing"
          v-model:value="this.record.tempDescription"
          size="small" style="width: 100px"
        />
        <span v-else>{{ this.record.description }}</span>
      </span>
      <n-button size="small" @click="this.editScriptDesc">{{ this.record.descriptionEditing ? '保存' : '编辑' }}</n-button>
    </div>
  </div>

  <div class="scriptContainer">
    <div class="scriptManagersContainer" style="display: inline-block; width: 1500px;">
      <div style="float: left; gap: 10px; display: flex;">
        <n-dropdown trigger="click" :options="this.devOptions" @select="updateDevice">
          <n-button class="btn" type="primary" style="width: 150px" @click="getDevices">选择设备</n-button>
        </n-dropdown>
        <n-button class="btn" type="primary" @click="recordingSwitch" style="width: 150px">开始/停止</n-button>
        <n-button class="btn" type="primary" @click="recordingInit" style="width: 150px">新建脚本</n-button>
        <n-button class="btn" type="primary" @click="scriptDiscard" style="width: 150px">删除脚本</n-button>
        <n-popconfirm :show-icon="false" @positive-click="this.doEnterText">
          <template #trigger>
            <n-button id="triggerInput" class="btn" type="info" style="width: 150px" @click="this.record.needInput = true">启用输入</n-button>
          </template>
          <n-input v-model:value="this.record.inputText" type="textarea" :disabled="!this.record.needInput" style="height: 45px; width: 200px" placeholder="请输入..."/>
        </n-popconfirm>
        <n-button class="btn" type="primary" style="width: 150px" @click="generateScriptDescription">更新脚本描述</n-button>
        <n-button class="btn" type="primary" @click="showModal.for_path_mutate = !showModal.for_path_mutate">路径变异</n-button>
        <n-modal v-model:show="showModal.for_path_mutate" preset="dialog" title="详情编辑" :style="{ width: '800px' }">
          <template #default>
            <div>
              <img :src="tempPathContext.screenWithBbox" style="max-width: 100%; max-height: 1000px; float: left;" alt=""/>
            </div>
            <div v-for="(item, index) in this.tempPathContext.newOperationInfo" :key="index">
              <n-input v-model:value="this.tempPathContext.newOperationInfo[index].new_action.type" style="width: 10%;" placeholder="输入内容"/>
              <n-input v-model:value="this.tempPathContext.newOperationInfo[index].new_action.target" style="width: 10%;" placeholder="输入内容"/>
              <n-input v-model:value="this.tempPathContext.newOperationInfo[index].new_action.description" style="width: 50%;" placeholder="输入内容"/>
              <n-input v-model:value="this.tempPathContext.newOperationInfo[index].description" style="width: 50%;" placeholder="输入内容"/>
              <n-button @click="this.tempPathContext.newOperationInfo.splice(index, 1)" size="tiny" type="error">删除</n-button>
            </div>
            <n-button type="primary" secondary size="small" @click="this.tempPathContext.newOperationInfo.push(
                {'new_action': {'type': 'tap', 'target': '', 'description': ''}, 'description': ''})" :disabled="this.tempPathContext.newOperationInfo >= 10">新增操作</n-button>
          </template>
          <template #action>
            <n-button @click="doPathMutate">生成变异结果</n-button>
            <n-button @click="onPathMutateCancel">取消</n-button>
            <n-button type="primary" @click="onPathMutateConfirm">确认</n-button>
          </template>
        </n-modal>
      </div>
      <div style="float: left; gap: 10px; display: flex">
        <n-button class="btn" type="primary" @click="updateDeviceConnection" style="width: 150px">连接/断开</n-button>
        <n-dropdown trigger="click" :options="this.scriptOptions" @select="handleScriptSelect">
          <n-button class="btn" type="primary" style="width: 150px" @click="updateScriptOptions(false)">选择脚本</n-button>
        </n-dropdown>
        <n-button class="btn" type="primary" @click="replayScript" style="width: 150px">回放脚本</n-button>
        <n-popconfirm :show-icon="false" @positive-click="this.doCreateAssert">
          <template #trigger>
            <n-button id="triggerAssert" class="btn" type="info" style="width: 150px">插入断言</n-button>
          </template>
          <n-input v-model:value="this.record.oracleText" type="textarea" style="height: 45px; width: 200px" placeholder="请输入..."/>
        </n-popconfirm>
        <n-button class="btn" type="primary" @click="prepare_for_mutation" style="width: 150px">变异准备</n-button>
        <n-button class="btn" type="primary" @click="showModal.for_input_data_mutate = !showModal.for_input_data_mutate">输入数据变异</n-button>
        <n-modal v-model:show="showModal.for_input_data_mutate" preset="dialog" title="详情编辑" :style="{ width: '800px' }">
          <template #default>
            <div v-for="(item, index) in this.tempInputTextList" :key="index">
              <n-input v-model:value="this.tempInputTextList[index][0]" style="width: 80%" placeholder="输入内容"/>
              <n-button @click="this.tempInputTextList.splice(index, 1)" size="tiny" type="error">删除</n-button>
            </div>
            <n-button type="primary" secondary size="small" @click="this.tempInputTextList.push([''])" :disabled="this.tempInputTextList.length >= 10">新增文本</n-button>
          </template>
          <template #action>
            <n-button @click="doInputDataMutate">生成变异结果</n-button>
            <n-button @click="onInputDataMutateCancel">取消</n-button>
            <n-button type="primary" @click="onInputDataMutateConfirm">确认</n-button>
          </template>
        </n-modal>
        <n-button class="btn" type="primary" @click="completeMutatingScript">完成变异</n-button>
      </div>
    </div>

    <div class="scriptDisplayContainer">
      <div v-for="(item, index) in this.record.opList" :key="index">
        <div class="operationItem" style="border: 2px solid #000000;">
          <div style="display: flex; gap: 20px; width: 900px;">
            <n-checkbox v-model:checked="item.checked" :disabled="item.mutate_type === 'NONE'" style="float: left;"/>
<!--            <n-button text class="operationDesc">{{ item.op_type }} -> {{item.widget_desc}} ~ {{item.intent}}</n-button>-->
            <n-button text class="operationDesc">{{ item.op_type }} -> {{item.widget_desc}}</n-button>
            <n-image class="widgetImage" style="float: left" :src="item.widget_img"/>
            <n-input
                v-if="item.op_type === 'tap_input'"
                v-model:value="item.op_params[2]"
                type="text" autosize :disabled="!item.edit_enable"
                style="min-width: 100px;"/>
            <n-input
                v-if="item.op_type === 'assert' && item.op_params.text"
                v-model:value="item.op_params.text"
                type="text" autosize :disabled="!item.edit_enable"
                style="min-width: 100px;"/>
          </div>
          <div style="float: right; display: inline-flex; gap: 5px;">
            <n-button v-if="item.replay === true" text class="btn" style="width: 10px;">✔</n-button>
            <n-button v-if="item.replay === false" text class="btn" style="width: 10px;">×</n-button>
            <n-button v-if="item.replay === undefined" text class="btn" style="width: 10px;">.</n-button>
            <n-button class="btn" type="primary" @click="removeOperation(index)" style="width: 70px;">删除</n-button>
            <n-button class="btn" type="primary" :disabled="!(item.op_type === 'tap_input' || item.op_type === 'assert' && item.op_params.text)" @click="editOperation(index)" style="width: 70px;">{{item.edit_btn_txt}}</n-button>
            <n-button class="btn" type="primary" @click="insertOperation(index)" style="width: 70px;">插入</n-button>
            <n-space vertical>
              <n-select size="large" v-model:value="item.mutate_type" :options="this.mutateOptions" @update:value="updateMutateType(index)" :consistent-menu-width="false"></n-select>
            </n-space>
          </div>
        </div>
      </div>
    </div>
  </div>

</div>
</template>

<style scoped>
#screenCap {
  width: 540px;
  height: 960px;
  border: 5px solid chartreuse;
}

.container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  gap: 20px;
}

.deviceContainer {
  display: grid;
  place-items: center;
}

.scriptContainer {
  display: grid;
  place-items: start;
}

.scriptInfoContainer {
  display: grid;
  text-align: left;
}

.scriptManagersContainer {
  display: flex;
  gap: 10px;
  justify-content: center;
  align-items: center;
}

.scriptDisplayContainer {
  width: 1500px;
  height: 800px;
}

.operationItem {
  width: 1450px;
  height: 60px;
  display: inline-flex;
}

.operationDesc {
  font-size: 16px;
}

.btn {
  margin: 10px 0;
  padding: 10px 20px;
  font-size: 16px;
  cursor: pointer;
  width: 155px;
}
</style>