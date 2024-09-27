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
const viewCurrentLayoutButton = document.querySelector('#task-card-current');

// Notification
const notification = document.querySelector("#notification");
const notificationMessage = document.querySelector("#notification-message");
const notificationCloseButton = document.querySelector("#notification-close");

// Task queue
const taskQueue = document.querySelector("#taskList");

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

    const taskCard = `<div id="task-card-${taskId}" class="task-card" style="border-left-color: #ffdd57;">
                    <div class="task-icon">
                        <span class="icon has-text-warning">
                            <i class="fas fa-spinner fa-spin"></i>
                        </span>
                    </div>
                    <div class="task-content">
                        <p class="task-name">${layoutName}</p>
                        <div class="tags">
                            <span class="tag is-warning task-status">${statusMsg}</span>

                            <span class="tag is-light">
                                <span class="icon-text">
                                    <span class="icon">
                                        <i class="fas fa-dumpster"></i>
                                    </span>
                                    <span>352</span>
                                </span>
                            </span>

                            <span class="tag is-light">
                                <span class="icon-text">
                                    <span class="icon">
                                        <i class="fas fa-people-group"></i>
                                    </span>
                                    <span>1000</span>
                                </span>
                            </span>

                            <span class="tag is-light">
                                <span class="icon-text">
                                    <span class="icon">
                                        <i class="fas fa-rotate"></i>
                                    </span>
                                    <span>150</span>
                                </span>
                            </span>
                        </div>
                    </div>
                </div>`
    document.querySelector("#taskList").innerHTML += taskCard;
}

function updateTaskCard(taskId, state, map, containers) {
    const taskCard = document.querySelector(`#task-card-${taskId}`);
    const taskIcon = taskCard.querySelector('.task-icon');
    const taskContent = taskCard.querySelector('.task-content');
    const taskStatus = taskContent.querySelector('.task-status');

    if (state === "SUCCESS") {
        // Change border color to green
        taskCard.style.borderLeftColor = "#23d160";

        // Change icon to check
        taskIcon.innerHTML = `<span class="icon has-text-success">
            <i class="fas fa-check"></i>
        </span>`;

        // Change status message to success
        taskStatus.classList.remove('is-warning');
        taskStatus.classList.add('is-success');
        taskStatus.innerHTML = "Completed";


        taskCard.addEventListener('click', function () {
            updateActiveTaskCard(taskCard)
            map.addContainers(containers);
        });

    } else if (state === "FAILURE") {
        taskCard.style.borderLeftColor = "#ff3860";
        taskIcon.innerHTML = `<span class="icon has-text-danger">
            <i class="fas fa-exclamation-triangle"></i>
        </span>`;
        taskStatus.innerHTML = "Failure";
    }
}

function updateActiveTaskCard(taskCard) {
    const taskCards = document.getElementsByClassName("task-card")
    console.log(taskCards)
    Array.from(taskCards).forEach(element => {
        element.classList.remove("task-card-selected")
        const buttonIndicator = element.querySelector(".view-button")
        if (buttonIndicator != null) {
            console.log(buttonIndicator)
            buttonIndicator.remove();
        }
    });
    taskCard.classList.add("task-card-selected")
    // Add view button
    taskCard.innerHTML += `<button class="button is-small view-button">
            <span class="icon is-small">
                <i class="fas fa-eye"></i>
            </span>
        </button>`;
}

export { hideLoadingScreen, optimizeButton, showNotification, initOptimizationLoading, endOptimizationLoading, addTaskCardToQueue, updateTaskCard, layoutName, viewCurrentLayoutButton, updateActiveTaskCard }