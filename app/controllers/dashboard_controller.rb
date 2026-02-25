class DashboardController < ApplicationController
  def index
    @patients = Patient.all.order(created_at: :desc)
    @recent_runs = WorkflowRun.includes(case: :patient).order(created_at: :desc).limit(10)
  end
end
