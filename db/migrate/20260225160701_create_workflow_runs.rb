class CreateWorkflowRuns < ActiveRecord::Migration[8.1]
  def change
    create_table :workflow_runs do |t|
      t.references :case, null: false, foreign_key: true
      t.string :status, default: "pending", null: false
      t.datetime :started_at
      t.datetime :completed_at
      t.text :error_message
      t.text :log_output

      t.timestamps
    end
  end
end
