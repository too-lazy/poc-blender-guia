class StatusController < ApplicationController
  def index
    @filter = params[:filter] || "all"

    @runs = WorkflowRun.includes(case: :patient)
                        .order(created_at: :desc)

    case @filter
    when "running"
      @runs = @runs.where(status: %w[pending running])
    when "completed"
      @runs = @runs.where(status: "completed")
    when "failed"
      @runs = @runs.where(status: "failed")
    end

    @runs = @runs.limit(50)

    @counts = {
      all: WorkflowRun.count,
      running: WorkflowRun.where(status: %w[pending running]).count,
      completed: WorkflowRun.where(status: "completed").count,
      failed: WorkflowRun.where(status: "failed").count
    }
  end
end
