## GitOps

### Prerequisite

We need a Ubuntu VM, which is configured as a self-hosted runner. This VM, should have network connectivity to the
Prism-Central and the clusters in consideration.
Click [here](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners) to read how to
configure self-hosted runner to your repository.

### Required parameters

Read about the required parameters to run the framework [here](../README.md#framework-usage).

### Github pipelines

We can use **Github workflows/ pipelines** to manage GitOps i.e using this repository to manage Infrastructure as a
Code (IaaC), that gets triggered from Github.
> A **Github workflow** is a configurable automated process that will run one or more jobs. Workflows are defined by a
> YAML file checked in to your repository and will run when triggered by an event in your repository, or they can be
> triggered manually, or at a defined schedule.

### How to auto-trigger pre-configured workflows

There are several pre-configured **Github workflows/ pipelines**. All the below-mentioned workflows are triggered by the
approval of a PR containing the configuration file changes.
Here is the step-by-step guide.

- Create a new branch/ use an existing branch other than `main`.
- Modify any of the following pre-configured configured files [config/pod-deploy.yml](pod-deploy.yml)
  , [config/pod-management-deploy.yml.yml](pod-management-deploy.yml.yml), [config/pod-management-config.yml](pod-management-config.yml.yml)
  , [config/pod-config.yml](pod-config.yml), [config/create-vm-workloads.yml](create-vm-workloads.yml)
  , [config/edge-ai.json](edge-ai.json) with the corresponding configuration changes for your environment.
- Create a **Pull-Request (PR)** from this branch to **main**.
- Get an approval for the changes.

That's it. The corresponding workflow/s kicks in. Below are the details of workflows that are triggered by the
configuration files changes.

- **Imaging workflow** - This Github workflow gets triggered when the file [config/pod-deploy.yml](pod-deploy.yml) is part
  of the PR. This GitHub workflow will setup the necessary Python environment and calls the framework as below
    ```sh
    > python main.py --workflow imaging -f config/pod-deploy.yml
    ```
- **Pod config workflow** - This Github workflow gets triggered when the file [config/pod-config.yml](pod-config.yml) is
  part of the PR. This GitHub workflow will setup the necessary Python environment and calls the framework as below
    ```sh
    > python main.py --workflow pod-config -f config/pod-config.yml
    ```
- **VM workloads workflow** - This Github workflow gets triggered when the
  file [config/create-vm-workloads.yml](create-vm-workloads.yml) is part of the PR. This Github workflow will setup the
  necessary Python environment and calls the framework as below
    ```sh
    > python main.py --workflow calm-vm-workloads -f config/create-vm-workloads.yml
    ```
- **Edge AI workload workflow** - This Github workflow gets triggered when the file [config/edge-ai.json](edge-ai.json)
  is part of the PR. This GitHub workflow will setup the necessary Python environment and calls the framework as below
    ```sh
    > python main.py --workflow calm-edgeai-vm-workload -f config/edge-ai.json
    ```  
- **Deploy Management PC workflow** - This Github workflow gets triggered when the file [config/pod-management-deploy.yml](pod-management-deploy.yml) is
  part of the PR. This GitHub workflow will setup the necessary Python environment and calls the framework as below
    ```sh
    > python main.py --workflow deploy-management-pc -f config/pod-management-deploy.yml.yml
    ```
- **Config Management PC workflow** - This Github workflow gets triggered when the file [config/pod-management-config.yml](pod-management-config.yml) is
  part of the PR. This GitHub workflow will setup the necessary Python environment and calls the framework as below
    ```sh
    > python main.py --workflow config-management-pc -f config/pod-management-config.yml.yml
    ```

> Note: The PR cannot contain configuration changes in multiple files, as they conflict with one another [config/pod-deploy.yml](pod-deploy.yml)
> , [config/pod-management-deploy.yml.yml](pod-management-deploy.yml.yml), [config/pod-management-config.yml](pod-management-config.yml.yml)
> , [config/pod-config.yml](pod-config.yml), [config/create-vm-workloads.yml](create-vm-workloads.yml)
> , [config/edge-ai.json](edge-ai.json). In the scenario where multiple configuration changes exist, only the first one in the below workflow chain would be triggered.
> **Imaging workflow -> Pod Management Deploy -> Pod Management Config -> Pod config workflow -> VM workloads workflow -> Edge AI workload workflow**.

## Snapshots of auto-trigger

- Modify any of the files configured for auto-trigger (**config/pod-deploy.yml/ config/pod-config.yml/ config/pod-management-deploy.yml/
  config/pod-management-config.yml config/create-vm-workloads.yml**) and commit to a new branch.  
  ![](../.github/images/new-branch.png)
- Create a PR.  
  ![](../.github/images/new-pr.png)
- Get approval for the PR. This triggers the workflow.  
  ![](../.github/images/approve-pr.png)
- Then monitor the workflow from `Actions` tab under `Trigger Python Workflows` section, click on latest workflow run
  and expand `Run python script` for streaming logs.  
  ![](../.github/images/workflow.png)
- The logs and input config file, used for the run will be pushed back to the branch that triggered the run.  
  ![](../.github/images/logs.png)

## Example of triggering workflows manually from the Github UI

- This workflow can be manually triggered from the `Actions` Tab in Github.  
  ![](../.github/images/actions.png)  
  ![](../.github/images/run_wf.png)
