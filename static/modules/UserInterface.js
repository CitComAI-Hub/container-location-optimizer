/* -------------------
---- UI elements ----
---------------------*/

// Loading screen
const loading = document.querySelector("#loading");
const dashboard = document.querySelector("#dashboard");

// Form
//const resetFormButton = document.querySelector("#reset-form");
const optimizeButton = document.querySelector('#optimize-button');
const layoutName = document.querySelector('#layout-name');
const viewCurrentLayout = document.querySelector('#task-card-current');
const taskList = document.querySelector("#taskList");

// Notification
const notification = document.querySelector("#notification");
const notificationMessage = document.querySelector("#notification-message");
const notificationCloseButton = document.querySelector("#notification-close");

// Task queue
const taskQueue = document.querySelector("#taskList");

// Settings panel
const settingsBtn = document.getElementById('settings-btn');
const settingsOverlay = document.getElementById('settings-overlay');
const closeBtn = document.getElementById('close-btn');

// Show the settings panel when the gear button is clicked
settingsBtn.addEventListener('click', () => {
    settingsOverlay.style.display = 'flex';
});

// Hide the settings panel when the close button is clicked
closeBtn.addEventListener('click', () => {
    settingsOverlay.style.display = 'none';
});

// Hide the settings panel when clicking outside of it (only inside the column)
settingsOverlay.addEventListener('click', (event) => {
    if (event.target === settingsOverlay) {
        settingsOverlay.style.display = 'none';
    }
});

/* -------------------
------- Events -------
---------------------*/

//resetFormButton.addEventListener("click", resetForm);
notificationCloseButton.addEventListener("click", hideNotification)

/* -------------------
---- UI functions ----
---------------------*/
function hideLoadingScreen() {
    loading.classList.add("is-hidden")
    dashboard.classList.remove("is-hidden")
}

// function resetForm() {
//     taskQueue.innerHTML = "";
// }

function showNotification(message, autoHide = false, type = "is-success") {
    // Clear classes
    notification.classList.remove("is-hidden");
    notification.classList.remove("hide");
    notification.classList.remove("is-success");
    notification.classList.remove("is-danger");

    if (type === "is-success") {
        notification.classList.add("is-success");
    } else {
        notification.classList.add("is-danger");
    }

    // Show
    notification.classList.add("show");
    notificationMessage.innerHTML = message;

    if (autoHide) {
        // Hide after 5 seconds
        setTimeout(hideNotification, 4000);
    }
}

function hideNotification() {
    notification.classList.remove("show");
    notification.classList.add("hide");
}

function initOptimizationLoading() {
    optimizeButton.classList.add('is-loading');
    optimizeButton.disabled = true;
    //resetFormButton.disabled = true;
}

function endOptimizationLoading() {
    optimizeButton.classList.remove('is-loading');
    optimizeButton.disabled = false;
    //resetFormButton.disabled = false;
}

function addTaskCardToQueue(taskId, layoutName, statusMsg, taskNumber) {

    if (layoutName === "") {
        layoutName = `Layout ${taskNumber}`;
    }

    const taskCard = `<details id="task-card-${taskId}" class="task-card">
                    <summary onclick="event.preventDefault()">
                        <span class="task-content icon-text">
                            <span class="task-name">${layoutName}</span>
                            <span class="icon has-text-warning task-icon">
                                <i class="fas fa-spinner fa-spin"></i>
                            </span>
                        </span>
                        <span class="task-increment">
                            
                        </span>
                        <span class="icon is-small icon-chevron hidden">
                            <i class="fas fa-chevron-down"></i>
                        </span>
                    </summary>
                    <div class="tags">
                            <span class="tag is-warning task-status">${statusMsg}</span>
                            <span class="tag is-light">
                                <span class="icon-text">
                                    <span class="icon">
                                        <i class="fas fa-dumpster" aria-hidden="true"></i>
                                    </span>
                                    <span>352</span>
                                </span>
                            </span>

                            <span class="tag is-light">
                                <span class="icon-text">
                                    <span class="icon">
                                        <i class="fas fa-people-group" aria-hidden="true"></i>
                                    </span>
                                    <span>1000</span>
                                </span>
                            </span>

                            <span class="tag is-light">
                                <span class="icon-text">
                                    <span class="icon">
                                        <i class="fas fa-rotate" aria-hidden="true"></i>
                                    </span>
                                    <span>150</span>
                                </span>
                            </span>
                    </div>
                </details>`;

    // Create a temporary container to hold the HTML string
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = taskCard;
    taskList.appendChild(tempDiv.firstChild);
}

function updateTaskCard(task, map, increment) {
    //.task_id, task.state, map, task.containers
    const taskCard = document.querySelector(`#task-card-${task.task_id}`);
    const taskIcon = taskCard.querySelector('.task-icon');
    const taskStatus = taskCard.querySelector('.task-status');
    const taskToggleButton = taskCard.querySelector('.icon-chevron');
    const taskIncrement = taskCard.querySelector('.task-increment');
    taskIncrement.innerHTML = `${increment}%<i class="fas fa-arrow-up" aria-hidden="true"></i>`;


    if (task.state === "SUCCESS") {
        // Change icon to check
        taskIcon.innerHTML = `<i class="fas fa-circle-check"></i></span>`;
        taskIcon.classList.remove('has-text-warning');
        taskIcon.classList.add('has-text-success');

        // Change status message to success
        taskStatus.classList.remove('is-warning');
        taskStatus.classList.add('is-success');
        taskStatus.innerHTML = "Completed";


        taskToggleButton.classList.remove('hidden');
        taskToggleButton.addEventListener('click', (event) => {
            taskCard.open = !taskCard.open; // Toggle the open state of the <details> element            
        });


        // Add click event to task card
        taskCard.addEventListener('click', (event) => {
            const fromToggleButton = event.target == taskToggleButton.querySelector('i');

            // Only update the map if the task card was clicked
            if (!fromToggleButton) {
                updateActiveTaskCard(taskCard)
                map.addContainers(task.containers);

                map.addVoronois(task.result.voronoi_polygons, task.result.voronoi_fitness);
            }

        });

    } else if (task.state === "FAILURE") {
        taskIcon.innerHTML = `<i class="fas fa-exclamation-triangle"></i>`;
        taskStatus.classList.remove('is-warning');
        taskStatus.classList.add('is-danger');
        taskStatus.innerHTML = "Failure";
    }
}

function updateActiveTaskCard(taskCard) {
    const taskCards = document.getElementsByClassName("task-card")
    Array.from(taskCards).forEach(element => {
        element.classList.remove("task-card-selected")
    });
    taskCard.classList.add("task-card-selected")
}

export { hideLoadingScreen, optimizeButton, showNotification, initOptimizationLoading, endOptimizationLoading, addTaskCardToQueue, updateTaskCard, layoutName, viewCurrentLayout, updateActiveTaskCard }