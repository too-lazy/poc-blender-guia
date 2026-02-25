class ChangePatientIdNullableOnCases < ActiveRecord::Migration[8.1]
  def change
    change_column_null :cases, :patient_id, true
    remove_foreign_key :cases, :patients
    add_foreign_key :cases, :patients, on_delete: :cascade, validate: true
  end
end
