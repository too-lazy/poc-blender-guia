class DashboardController < ApplicationController
  def index
    @patients = Patient.all.order(created_at: :desc)
    @recent_runs = WorkflowRun.includes(case: :patient).order(created_at: :desc).limit(10)
    @patient_count = Patient.count
    @case_count = Case.count
    @run_count = WorkflowRun.count
  end
end
