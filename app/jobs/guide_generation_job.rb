class GuideGenerationJob < ApplicationJob
  queue_as :default

  BLENDER_SCRIPT = Rails.root.join("src", "cli.py").to_s

  def perform(workflow_run_id)
    run = WorkflowRun.find(workflow_run_id)
    dental_case = run.case
    run.update!(status: "running", started_at: Time.current)

    Dir.mktmpdir("guide_generation") do |tmpdir|
      upper_path = File.join(tmpdir, "upper.stl")
      lower_path = File.join(tmpdir, "lower.stl")
      screws_path = File.join(tmpdir, "screws.json")
      guide_stl_path = File.join(tmpdir, "guide.stl")
      output_path = File.join(tmpdir, "guide_render.png")

      # Download STL arches
      download_attachment(dental_case.upper_arch_file, upper_path)
      download_attachment(dental_case.lower_arch_file, lower_path)

      # Write screw positions JSON
      File.write(screws_path, dental_case.screw_positions.to_json)

      cmd = [
        "blender", "--background", "--python", BLENDER_SCRIPT,
        "--",
        "--upper", upper_path,
        "--lower", lower_path,
        "--screws", screws_path,
        "--output-guide", guide_stl_path,
        output_path
      ]

      log_output = []
      IO.popen(cmd, err: [ :child, :out ]) do |io|
        io.each_line { |line| log_output << line }
      end

      if $?.success?
        # Attach guide STL
        if File.exist?(guide_stl_path)
          dental_case.guide_stl_file.attach(
            io: File.open(guide_stl_path),
            filename: "guide_#{run.id}.stl",
            content_type: "model/stl"
          )
        end

        # Attach render
        if File.exist?(output_path)
          run.render_output.attach(
            io: File.open(output_path),
            filename: "guide_render_#{run.id}.png",
            content_type: "image/png"
          )
        end

        run.update!(
          status: "completed",
          completed_at: Time.current,
          log_output: log_output.join
        )
        dental_case.update!(status: "completed")
      else
        run.update!(
          status: "failed",
          completed_at: Time.current,
          error_message: "Blender exited with code #{$?.exitstatus}",
          log_output: log_output.join
        )
        dental_case.update!(status: "failed")
      end
    end
  rescue => e
    run = WorkflowRun.find_by(id: workflow_run_id)
    if run
      run.update!(
        status: "failed",
        completed_at: Time.current,
        error_message: e.message,
        log_output: e.backtrace&.first(20)&.join("\n")
      )
      run.case.update!(status: "failed")
    end
    raise
  end

  private

  def download_attachment(attachment, dest_path)
    File.open(dest_path, "wb") do |f|
      attachment.download { |chunk| f.write(chunk) }
    end
  end
end
