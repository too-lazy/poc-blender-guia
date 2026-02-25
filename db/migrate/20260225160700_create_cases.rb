class CreateCases < ActiveRecord::Migration[8.1]
  def change
    create_table :cases do |t|
      t.references :patient, null: false, foreign_key: true
      t.text :description
      t.string :status, default: "pending", null: false

      t.timestamps
    end
  end
end
