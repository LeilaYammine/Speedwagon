import abc
import logging

import typing

import forseti.job
import forseti.worker
import forseti.workflows
import forseti.tasks
from forseti import worker
import forseti.gui


class TaskFailed(Exception):
    pass


class AbsRunner(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def run(
            self,
            parent,
            job: forseti.job.AbsJob,
            options: dict,
            logger: logging.Logger,
            completion_callback=None
    ) -> None:
        pass


class RunRunner:
    def __init__(self, strategy: AbsRunner) -> None:
        self._strategy = strategy

    def run(
            self,
            parent,
            tool: forseti.job.AbsJob,
            options: dict,
            logger: logging.Logger,
            completion_callback=None
    ) -> None:
        self._strategy.run(parent, tool, options, logger, completion_callback)


class UsingExternalManager(AbsRunner):

    def __init__(
            self,
            manager: worker.ToolJobManager,
            on_success,
            on_failure
    ) -> None:

        self._manager = manager
        self._on_success = on_success
        self._on_failure = on_failure

    def run(self,
            parent,
            job: forseti.job.AbsJob,
            options: dict,
            logger: logging.Logger,
            completion_callback=None):

        try:
            with self._manager.open(options=options,
                                    tool=job,
                                    parent=parent) as runner:

                def update_progress(current: int, total: int):

                    if total != runner.dialog.maximum():
                        runner.dialog.setMaximum(total)
                    if current != runner.dialog.value():
                        runner.dialog.setValue(current)

                    if current == total:
                        runner.dialog.accept()

                if isinstance(job, forseti.job.AbsTool):
                    runner.abort_callback = self.on_runner_aborted
                    logger.addHandler(runner.progress_dialog_box_handler)
                    runner.dialog.setRange(0, 0)

                    i = -1
                    for i, new_setting in \
                            enumerate(job.discover_task_metadata(**options)):
                        new_job = job.new_job()
                        self._manager.add_job(new_job(), new_setting)
                    logger.info("Found {} jobs".format(i + 1))
                    runner.dialog.setMaximum(i)

                    self._manager.start()

                    runner.dialog.show()

                    results = list()
                    for result in self._manager.get_results(update_progress):
                        results.append(result)
                    logger.removeHandler(runner.progress_dialog_box_handler)

                    self._on_success(results, job.on_completion)
        except Exception as e:
            self._on_failure(e)

    def on_runner_aborted(self):
        self._manager.abort()


class UsingExternalManagerForAdapter(AbsRunner):

    def __init__(self, manager: worker.ToolJobManager) -> None:
        self._manager = manager

    def _update_progress(self, runner, current: int, total: int):

        if total != runner.dialog.maximum():
            runner.dialog.setMaximum(total)
        if current != runner.dialog.value():
            runner.dialog.setValue(current)

        if current == total:
            runner.dialog.accept()

    def run(
            self,
            parent,
            job: forseti.job.AbsJob,
            options: dict,
            logger: logging.Logger,
            completion_callback=None
    ) -> None:

        results: typing.List[typing.Any] = []

        if isinstance(job, forseti.job.AbsWorkflow):

            try:
                pre_results = self._run_pre_tasks(parent, job, options, logger)

                results += pre_results

                if isinstance(job, forseti.job.Workflow):
                    new_options = self._get_additional_options(parent,
                                                               job,
                                                               options,
                                                               pre_results)
                    if new_options:
                        options = {**options, **new_options}

            except TaskFailed as e:

                logger.error(
                    "Job stopped during pre-task phase. Reason: {}".format(e)
                )

                return

            try:
                results += self._run_main_tasks(parent,
                                                job,
                                                options,
                                                pre_results,
                                                logger)

            except TaskFailed as e:

                logger.error(
                    "Job stopped during main tasks phase. Reason: {}".format(e)
                )

                return

            try:
                results += self._run_post_tasks(parent,
                                                job,
                                                options,
                                                results,
                                                logger)

            except TaskFailed as e:

                logger.error(
                    "Job stopped during post-task phase. Reason: {}".format(e)
                )

                return

            logger.debug("Generating report")
            report = job.generate_report(results, **options)
            if report:
                logger.info(report)

    def _run_main_tasks(
            self,
            parent,
            job: forseti.job.AbsWorkflow,
            options,
            pretask_results,
            logger
    ) -> list:

        results = []

        with self._manager.open(parent=parent,
                                runner=worker.WorkRunnerExternal3) as runner:

            runner.abort_callback = self._manager.abort
            i = -1
            runner.dialog.setRange(0, 0)
            runner.dialog.setWindowTitle(job.name)
            try:
                logger.addHandler(runner.progress_dialog_box_handler)

                # Run the main tasks. Keep track of the progress
                for new_task_metadata \
                        in job.discover_task_metadata(pretask_results,
                                                      **options):

                    main_task_builder = forseti.tasks.TaskBuilder(
                        forseti.tasks.MultiStageTaskBuilder()
                    )

                    job.create_new_task(main_task_builder, **new_task_metadata)

                    new_task = main_task_builder.build_task()
                    for subtask in new_task.subtasks:
                        i += 1

                        adapted_tool = forseti.worker.SubtaskJobAdapter(
                            subtask
                        )

                        self._manager.add_job(adapted_tool,
                                              adapted_tool.settings)

                logger.info("Found {} jobs".format(i + 1))
                runner.dialog.setMaximum(i)
                self._manager.start()

                runner.dialog.show()

                main_results = self._manager.get_results(
                    lambda x, y: self._update_progress(runner, x, y)
                )

                for result in main_results:
                    # for f in self._manager.futures:
                    #     print(f)
                    if result is not None:
                        results.append(result)
                if runner.was_aborted:
                    raise TaskFailed("User Aborted")
            finally:
                logger.removeHandler(runner.progress_dialog_box_handler)
            return results

    def _run_post_tasks(self, parent, job, options, results, logger) -> list:
        _results = []
        with self._manager.open(parent=parent,
                                runner=worker.WorkRunnerExternal3) as runner:

            runner.dialog.setRange(0, 0)
            try:
                logger.addHandler(runner.progress_dialog_box_handler)

                finalization_task_builder = forseti.tasks.TaskBuilder(
                    forseti.tasks.MultiStageTaskBuilder()
                )

                job.completion_task(finalization_task_builder,
                                    results,
                                    **options)

                task = finalization_task_builder.build_task()
                for subtask in task.main_subtasks:
                    adapted_tool = forseti.worker.SubtaskJobAdapter(subtask)
                    self._manager.add_job(adapted_tool, adapted_tool.settings)
                self._manager.start()

                post_results = self._manager.get_results(
                    lambda x, y: self._update_progress(runner, x, y)
                )

                for post_result in post_results:
                    if post_result is not None:
                        _results.append(post_result)

                runner.dialog.accept()
                runner.dialog.close()
                if runner.was_aborted:
                    raise TaskFailed("User Aborted")
                return _results
            finally:
                logger.removeHandler(runner.progress_dialog_box_handler)

    def _run_pre_tasks(self, parent, job, options, logger):
        results = []

        with self._manager.open(parent=parent,
                                runner=worker.WorkRunnerExternal3) as runner:

            runner.dialog.setRange(0, 0)
            logger.addHandler(runner.progress_dialog_box_handler)

            try:
                task_builder = forseti.tasks.TaskBuilder(
                    forseti.tasks.MultiStageTaskBuilder()
                )

                job.initial_task(task_builder, **options)

                task = task_builder.build_task()
                for subtask in task.main_subtasks:
                    adapted_tool = forseti.worker.SubtaskJobAdapter(subtask)
                    self._manager.add_job(adapted_tool, adapted_tool.settings)

                self._manager.start()

                post_results = self._manager.get_results(
                    lambda x, y: self._update_progress(runner, x, y)
                )

                for post_result in post_results:
                    if post_result is not None:
                        results.append(post_result)

                runner.dialog.accept()
                runner.dialog.close()
                if runner.was_aborted:
                    raise TaskFailed("User Aborted")
                return results
            finally:
                logger.removeHandler(runner.progress_dialog_box_handler)
    @staticmethod
    def _get_additional_options(parent, job, options, pretask_results) -> typing.Optional[dict]:

        return job.get_additional_info(parent, options, pretask_results)
