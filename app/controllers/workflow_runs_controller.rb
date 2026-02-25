class WorkflowRunsController < ApplicationController
  def show
    @patient = Patient.find(params[:patient_id])
    @case = @patient.cases.find(params[:case_id])
    @run = @case.workflow_runs.find(params[:id])
  end
end
