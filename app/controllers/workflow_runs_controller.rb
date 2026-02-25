class WorkflowRunsController < ApplicationController
  before_action :set_run

  def show
  end

  private

  def set_run
    if params[:patient_id]
      @patient = Patient.find(params[:patient_id])
      @case = @patient.cases.find(params[:case_id])
      @run = @case.workflow_runs.find(params[:id])
    else
      @run = WorkflowRun.find(params[:id])
      @case = @run.case
      @patient = @case.patient
    end
  end
end
