import { HttpClient } from './HttpClient.js';

export class Optimizer {

    constructor() {
        this.httpClient = new HttpClient();
    }

    async startTask() {
        const taskId = await this.httpClient.get('start_task');
        return taskId.task_id;
    }

    async getTask(taskId) {
        const result = await this.httpClient.get('task_status', { task_id: taskId });
        return result;
    }
}